import json  
import os  
import time  #
from flask import 
import openai  
from openai import OpenAI  
import custom_functions  
from waitress import serve  

# Ortam değişkenlerinden API anahtarlarını al
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")


app = Flask(__name__)


client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"OpenAI-Beta": "assistants=v2"}  # v2 API kullanımını aktif eder
)


assistant_id = custom_functions.create_assistant(client)  # create_assistant() fonksiyonu functions.py içinde tanımlı

# Yeni bir konuşma (thread) başlatmak için GET endpoint
@app.route('/start', methods=['GET'])
def start_conversation():
  print("Starting a new conversation...")  # Terminale yazdır
  thread = client.beta.threads.create()  # Yeni bir thread (konuşma dizisi) oluştur
  print(f"New thread created with ID: {thread.id}")  # Thread ID'sini terminale yazdır
  return jsonify({"thread_id": thread.id})  # Kullanıcıya thread ID'sini döndür

# Kullanıcıdan mesaj alıp asistandan yanıt döndürmek için POST endpoint
@app.route('/chat', methods=['POST'])
def chat():
  data = request.json  # İstekten gelen JSON verisini al
  thread_id = data.get('thread_id')  # thread_id'yi al
  user_input = data.get('message', '')  # Kullanıcının mesajını al

 
  if not thread_id:
    print("Error: Missing thread_id")
    return jsonify({"error": "Missing thread_id"}), 400

  print(f"Received message: {user_input} for thread ID: {thread_id}") 

  # Kullanıcı mesajını thread'e ekle
  client.beta.threads.messages.create(thread_id=thread_id,
                                   role="user",  
                                   content=user_input) 

  # Asistanı çalıştır
  run = client.beta.threads.runs.create(thread_id=thread_id,
                                     assistant_id=assistant_id)  

  # Asistanın cevabı hazır mı veya işlem (function call) gerekiyor mu kontrol et
  while True:
    run_status = client.beta.threads.runs.retrieve(thread_id=thread_id,
                                                run_id=run.id)  
    if run_status.status == 'completed':
      break  
    elif run_status.status == 'requires_action':
      for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
        if tool_call.function.name == "create_lead":
          

          # Fonksiyon için gerekli parametreleri 
          arguments = json.loads(tool_call.function.arguments)
          name = arguments.get('name','')
          company_name = arguments.get('company_name','')
          phone = arguments.get('phone','')
          email = arguments.get('email','')

          # custom_functions içindeki create_lead fonksiyonu ile işlem yap
          output = custom_functions.create_lead(name, company_name, phone, email)

          # Asistana fonksiyon sonucu döndür
          client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                    run_id=run.id,
                                                    tool_outputs=[{
                                                        "tool_call_id": tool_call.id,
                                                        "output": json.dumps(output)  # Fonksiyonun çıktısını asistana ilet
                                                    }])
      time.sleep(1)  # API'ye çok sık istek atılmaması için bekleme

 
  messages = client.beta.threads.messages.list(thread_id=thread_id)
  response = messages.data[0].content[0].text.value  # Asistanın cevabını al

  print(f"Assistant response: {response}")  # Cevabı terminale yazdır
  return jsonify({"response": response})  # Cevabı kullanıcıya JSON olarak gönder

# Flask uygulamasını başlat
if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8080)  # Tüm ağdan erişilebilir şekilde 8080 portunda başlat
