import os
import pytz
import asyncio
import traceback
import json
import uuid
import warnings
from typing import Dict, Any
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import async_create_deep_agent
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage
from tavily import TavilyClient
from dotenv import load_dotenv
import datetime
from prompts import (
    PERSONAL_ASSISTANT_PROMPT,
    subagents
)

# Suppress pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Load environment variables
load_dotenv()

# Nigeria timezone
NIGERIA_TZ = pytz.timezone("Africa/Lagos")

# Initialize Tavily client
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY environment variable is not set")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# Validate GROQ_API_KEY
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set")

# Initialize LLM for parsing user responses
llm = ChatGroq(model=os.getenv("MODEL", "moonshotai/kimi-k2-instruct-0905"))

# MCP server configuration with absolute paths
server_dir = os.path.abspath("servers")
mcp_client = MultiServerMCPClient(
    {
        "generate_audio": {
            "command": "python",
            "args": [os.path.join(server_dir, "generate_audio_server.py")],
            "transport": "stdio",
        },
        "send_whatsapp_message": {
            "command": "python",
            "args": [os.path.join(server_dir, "send_whatsapp_message_server.py")],
            "transport": "stdio",
        },
        "internet_search": {
            "command": "python",
            "args": [os.path.join(server_dir, "internet_search_server.py")],
            "transport": "stdio",
        },
        "send_email": {
            "command": "python",
            "args": [os.path.join(server_dir, "send_email_server.py")],
            "transport": "stdio",
        },
        "send_slack_message": {
            "command": "python",
            "args": [os.path.join(server_dir, "send_slack_message_server.py")],
            "transport": "stdio",
        },
    }
)

async def parse_user_response(action: str, args: Dict[str, Any], options: Dict[str, bool], user_response: str, valid_tools: list) -> Dict[str, Any]:
    if not user_response.strip():
        return {"type": "respond", "args": "No response provided, please clarify"}
    
    # Sanitize action to ensure it's a clean string
    action = str(action).strip()
    print(f"DEBUG: Parsing response - action: {action}, args: {args}, user_response: {user_response}")
    
    try:
        # Dynamic f-string prompt remains here for runtime formatting
        prompt = f"""You are an assistant that interprets natural language user responses during a Human-in-the-Loop interrupt for a tool-using agent. The agent has paused due to a tool call requiring approval. Your task is to interpret the user's intent from their natural language response and classify it as one of: 'accept', 'edit', or 'respond', formatting the output for resuming the agent's execution.

Available tools: {', '.join(valid_tools)}

Input context:
- Current action: {action}
- Current args: {json.dumps(args, ensure_ascii=False)}
- User response: {user_response}

Instructions:
1. If the user response is empty or invalid, default to 'respond' with args "No response provided, please clarify."
2. Interpret the user's natural language response to determine their intent:
   - 'accept': User wants to proceed with the current action and args unchanged (e.g., "Looks good", "Send it", "Okay", "Go ahead").
   - 'edit': User wants to change the action (e.g., switch from send_whatsapp_message to send_slack_message) or modify key parameters (e.g., phone_number, recipient_id, message content).
   - 'respond': User provides clarification or additional information without changing the action (e.g., updating the message content for send_whatsapp_message).
3. For 'edit':
   - Identify the new action (if changed) from the available tools.
   - Extract new args as a JSON object, ensuring compatibility with the tool's requirements (e.g., send_slack_message requires message, recipient_id).
4. For 'respond':
   - Capture the response as a string to guide the agent (e.g., new message content or instructions). Handle informal or partial inputs by inferring intent.
5. For 'accept':
   - Return an empty dict to proceed with the original action and args.
6. Output a JSON object with:
   - type: "accept", "edit", or "respond"
   - args: For 'edit', a dict with {{"action": str, "args": dict}}. For 'respond', a string. For 'accept', an empty dict.
7. Handle natural language responses by inferring intent without requiring explicit terms like "accept" or "edit". For example:
   - "Send it to his WhatsApp instead, +2348036926719" should be classified as 'edit' with a new action and args.
   - "Change the message to say meeting cancelled" should be classified as 'respond'.
   - "Looks fine" should be classified as 'accept'.

Examples:
1. Input:
   - Current action: send_whatsapp_message
   - Current args: {{"message": "Hi Nonso", "phone_number": "+2348012345678"}}
   - User response: Go ahead
   Output:
   {{
     "type": "accept",
     "args": {{}}
   }}

2. Input:
   - Current action: send_whatsapp_message
   - Current args: {{"message": "Hi", "phone_number": "+2348012345678"}}
   - User response: Send him a DM instead. 'Alaye! Kilon sele?' U1234567890
   Output:
   {{
     "type": "edit",
     "args": {{
       "action": "send_slack_message",
       "args": {{
         "message": "Alaye! Kilon sele?",
         "recipient_id": "U1234567890"
       }}
     }}
   }}

3. Input:
   - Current action: send_whatsapp_message
   - Current args: {{"message": "Hi", "phone_number": "+2348012345678"}}
   - User response: Nah, tell him the meeting is cancelled
   Output:
   {{
     "type": "respond",
     "args": "Change the message to 'Meeting is cancelled'"
   }}

4. Input:
   - Current action: send_whatsapp_message
   - Current args: {{"message": "Hi", "phone_number": "+2348012345678"}}
   - User response: 
   Output:
   {{
     "type": "respond",
     "args": "No response provided, please clarify"
   }}

5. Input:
   - Current action: send_email
   - Current args: {{"body": "Hi Nonso,\n\nJust a quick reminder that tomorrow's meeting is scheduled for 5 PM.\n\nBest regards", "recipient_email": "chinonsoodiakaaws@gmail.com", "subject": "Tomorrow's Meeting"}}
   - User response: Send it to his WhatsApp instead. Tell him tomorrow's meeting is by 5pm. +2348036926719
   Output:
   {{
     "type": "edit",
     "args": {{
       "action": "send_whatsapp_message",
       "args": {{
         "message": "Tomorrow's meeting is by 5 PM",
         "phone_number": "+2348036926719"
       }}
     }}
   }}

Now, process the input and provide the JSON output.
"""
        print(f"DEBUG: Formatted prompt: {prompt[:500]}...")  # Truncate for readability
    except Exception as e:
        print(f"ERROR: Failed to format prompt: {str(e)}")
        return {"type": "respond", "args": f"Error formatting prompt: {str(e)}"}
    
    try:
        response = await llm.ainvoke(prompt)
        print(f"DEBUG: LLM response: {response.content}")
        parsed_response = json.loads(response.content)
        # Validate edit action against available tools
        if parsed_response["type"] == "edit" and parsed_response["args"].get("action"):
            new_action = parsed_response["args"]["action"]
            if new_action not in valid_tools:
                print(f"ERROR: Invalid tool in edit response: {new_action}")
                return {"type": "respond", "args": f"Invalid tool '{new_action}'. Available tools: {', '.join(valid_tools)}"}
        return parsed_response
    except json.JSONDecodeError:
        print(f"ERROR: Failed to parse LLM response: {response.content}")
        return {"type": "respond", "args": f"Invalid LLM response: {response.content}"}
    except Exception as e:
        print(f"ERROR: LLM invocation failed: {str(e)}")
        return {"type": "respond", "args": f"LLM invocation failed: {str(e)}"}

async def main():
    try:
        # Fetch MCP tools
        print("Fetching MCP tools...")
        mcp_tools = await mcp_client.get_tools()
        valid_tools = [tool.name for tool in mcp_tools]
        print(f"Fetched {len(mcp_tools)} tools: {valid_tools}")

        # Initialize checkpointer
        checkpointer = InMemorySaver()

        # Create agent with interrupt config for HITL
        print("Creating agent...")
        agent = async_create_deep_agent(
            model=llm,
            tools=mcp_tools,
            subagents=subagents,
            instructions=PERSONAL_ASSISTANT_PROMPT,
            checkpointer=checkpointer,
            interrupt_config={
                "send_whatsapp_message": {
                    "allow_ignore": False,
                    "allow_respond": True,
                    "allow_edit": True,
                    "allow_accept": True,
                },
                "send_email": {
                    "allow_ignore": False,
                    "allow_respond": True,
                    "allow_edit": True,
                    "allow_accept": True,
                },
                "send_slack_message": {
                    "allow_ignore": False,
                    "allow_respond": True,
                    "allow_edit": True,
                    "allow_accept": True,
                },
                #"internet_search": False,
                #"generate_audio": False,
            }
        )
        print("Agent created successfully.")

        # Generate unique thread ID
        thread_id = str(uuid.uuid4())
        print(f"Generated thread_id: {thread_id}")

        # Main interaction loop
        while True:
            # Get user input with timestamp
            current_time = datetime.datetime.now(NIGERIA_TZ).strftime("%I:%M %p WAT on %A, %B %d, %Y")
            try:
                user_input = input(f"\n[{current_time}] Enter your query (or 'exit' to stop): ").strip()
            except KeyboardInterrupt:
                print("\nInput interrupted. Exiting...")
                break

            if user_input.lower() == "exit":
                print("Exiting...")
                break

            # Process the query
            config = {"configurable": {"thread_id": thread_id}}
            print(f"Processing query: {user_input}")
            input_data = {"messages": [HumanMessage(content=user_input)], "current_time": current_time}

            # Stream the initial execution
            async for chunk in agent.astream(input_data, config=config, stream_mode="values"):
                if "messages" in chunk:
                    chunk["messages"][-1].pretty_print()

            # Check for interrupts
            state = agent.get_state(config)
            while state.interrupts:
                intr = state.interrupts[0]
                print("\nInterrupt detected (via state):")

                # Extract action/args
                action_request = getattr(intr.value, "action_request", None) if hasattr(intr.value, "action_request") else None
                if action_request:
                    action = action_request["action"]
                    args = action_request["args"]
                    description = getattr(intr.value, "description", f"Proposed: {action} with {args}")
                    config_options = getattr(intr.value, "config", {"allow_accept": True, "allow_edit": True, "allow_respond": True})
                else:
                    messages = state.values["messages"]
                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                        tc = last_msg.tool_calls[0]
                        action = tc["name"]
                        args = tc["args"]
                        description = f"Proposed tool call: {action} with args {args}"
                        config_options = {"allow_accept": True, "allow_edit": True, "allow_respond": True}
                    else:
                        print("No tool call found in interrupt.")
                        resume_value = [{"type": "respond", "args": "No tool call found in interrupt"}]
                        command = Command(resume=resume_value)
                        async for resume_chunk in agent.astream(command, config=config, stream_mode="values"):
                            if "messages" in resume_chunk:
                                resume_chunk["messages"][-1].pretty_print()
                        state = agent.get_state(config)
                        continue

                print(description)
                print("\nDo you want to proceed with this, make changes, or cancel? (or 'exit' to stop)")
                try:
                    user_response = input("Your response: ").strip()
                except KeyboardInterrupt:
                    print("\nInterrupt response interrupted. Canceling action.")
                    resume_value = [{"type": "response", "args": "Action canceled due to interruption"}]
                    command = Command(resume=resume_value)
                    async for resume_chunk in agent.astream(command, config=config, stream_mode="values"):
                        if "messages" in resume_chunk:
                            resume_chunk["messages"][-1].pretty_print()
                    state = agent.get_state(config)
                    continue

                if user_response.lower() == "exit":
                    print("Exiting...")
                    return

                # Parse user response
                parsed_response = await parse_user_response(action, args, config_options, user_response, valid_tools)
                command_type = parsed_response["type"]
                command_args = parsed_response["args"]

                # Build resume value (aligned with LangGraph HITL)
                if command_type == "accept" and config_options.get("allow_accept"):
                    resume_value = [{"type": "accept"}]  # Empty args for accept
                elif command_type == "edit" and config_options.get("allow_edit"):
                    resume_value = [{"type": "edit", "args": command_args}]  # Nested action/args
                elif command_type == "respond" and config_options.get("allow_respond"):
                    resume_value = [{"type": "response", "args": command_args}]  # String feedback
                else:
                    print(f"Invalid or disallowed action: {command_type}")
                    resume_value = [{"type": "respond", "args": f"Invalid or disallowed action: {command_type}"}]
                    command = Command(resume=resume_value)
                    async for resume_chunk in agent.astream(command, config=config, stream_mode="values"):
                        if "messages" in resume_chunk:
                            resume_chunk["messages"][-1].pretty_print()
                    state = agent.get_state(config)
                    continue

                # Resume execution
                command = Command(resume=resume_value)
                async for resume_chunk in agent.astream(command, config=config, stream_mode="values"):
                    if "messages" in resume_chunk:
                        resume_chunk["messages"][-1].pretty_print()

                # Refresh state
                state = agent.get_state(config)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())