import json  # JSON verisini işlemek için kullanılır
import os  # Ortam değişkenlerini (API_KEY gibi) okumak için kullanılır
import time  # Bekleme işlemleri için kullanılır (sleep gibi)
from flask import Flask, request, jsonify  # Flask ile web sunucusu ve API endpoint'leri için
import openai  # OpenAI kitaplığı, API'ye bağlanmak için
from openai import OpenAI  # OpenAI istemcisini kullanmak için
import custom_functions  # Kendi yazdığımız yardımcı fonksiyonları içeren dosya (functions.py)
from waitress import serve  # Flask'ı production ortamında çalıştırmak için sunucu

# Ortam değişkenlerinden API anahtarlarını al
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")

# Flask uygulaması oluştur
app = Flask(__name__)

# OpenAI istemcisini başlat, Assistant v2 API'si kullanılacak
client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"OpenAI-Beta": "assistants=v2"}  # v2 API kullanımını aktif eder
)

# OpenAI asistanı oluştur ya da mevcut asistanı yükle
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

  # thread_id eksikse hata döndür
  if not thread_id:
    print("Error: Missing thread_id")
    return jsonify({"error": "Missing thread_id"}), 400

  print(f"Received message: {user_input} for thread ID: {thread_id}")  # Gelen mesajı terminale yaz

  # Kullanıcı mesajını thread'e ekle
  client.beta.threads.messages.create(thread_id=thread_id,
                                   role="user",  # Mesaj kullanıcıdan geliyor
                                   content=user_input)  # Mesaj içeriği

  # Asistanı çalıştır
  run = client.beta.threads.runs.create(thread_id=thread_id,
                                     assistant_id=assistant_id)  # Belirli asistana mesajı işlemesi için görev başlat

  # Asistanın cevabı hazır mı veya işlem (function call) gerekiyor mu kontrol et
  while True:
    run_status = client.beta.threads.runs.retrieve(thread_id=thread_id,
                                                run_id=run.id)  # Run durumunu kontrol et
    if run_status.status == 'completed':
      break  # Cevap hazırsa döngüden çık
    elif run_status.status == 'requires_action':
      # Asistan bir fonksiyon çağırmak istiyorsa
      for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
        if tool_call.function.name == "create_lead":
          # create_lead fonksiyonu çağırılıyor

          # Fonksiyon için gerekli parametreleri al
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

  # Konuşmadaki son mesajı al (asistan cevabı)
  messages = client.beta.threads.messages.list(thread_id=thread_id)
  response = messages.data[0].content[0].text.value  # Asistanın cevabını al

  print(f"Assistant response: {response}")  # Cevabı terminale yazdır
  return jsonify({"response": response})  # Cevabı kullanıcıya JSON olarak gönder

# Flask uygulamasını başlat (waitress ile)
if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8080)  # Tüm ağdan erişilebilir şekilde 8080 portunda başlat
