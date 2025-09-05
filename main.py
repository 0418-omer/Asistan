import json  
import os  
import time  #
from flask import 
import openai  
from openai import OpenAI  
import custom_functions  
from waitress import serve  


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")


app = Flask(__name__)


client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"OpenAI-Beta": "assistants=v2"}  
)


assistant_id = custom_functions.create_assistant(client)  


@app.route('/start', methods=['GET'])
def start_conversation():
  print("Starting a new conversation...")  
  thread = client.beta.threads.create()  
  print(f"New thread created with ID: {thread.id}")  
  return jsonify({"thread_id": thread.id})  


@app.route('/chat', methods=['POST'])
def chat():
  data = request.json  
  thread_id = data.get('thread_id')  
  user_input = data.get('message', '')  

 
  if not thread_id:
    print("Error: Missing thread_id")
    return jsonify({"error": "Missing thread_id"}), 400

  print(f"Received message: {user_input} for thread ID: {thread_id}") 

 
  client.beta.threads.messages.create(thread_id=thread_id,
                                   role="user",  
                                   content=user_input) 

  
  run = client.beta.threads.runs.create(thread_id=thread_id,
                                     assistant_id=assistant_id)  

  
  while True:
    run_status = client.beta.threads.runs.retrieve(thread_id=thread_id,
                                                run_id=run.id)  
    if run_status.status == 'completed':
      break  
    elif run_status.status == 'requires_action':
      for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
        if tool_call.function.name == "create_lead":
          

          
          arguments = json.loads(tool_call.function.arguments)
          name = arguments.get('name','')
          company_name = arguments.get('company_name','')
          phone = arguments.get('phone','')
          email = arguments.get('email','')

          
          output = custom_functions.create_lead(name, company_name, phone, email)

          # Asistana fonksiyon sonucu döndür
          client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                    run_id=run.id,
                                                    tool_outputs=[{
                                                        "tool_call_id": tool_call.id,
                                                        "output": json.dumps(output)  
                                                    }])
      time.sleep(1) 

 
  messages = client.beta.threads.messages.list(thread_id=thread_id)
  response = messages.data[0].content[0].text.value  

  print(f"Assistant response: {response}")  
  return jsonify({"response": response})  

# Flask uygulamasını başlat
if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8080)  
