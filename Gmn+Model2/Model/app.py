# app.py by Ephesta

import joblib
import pandas as pd
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import datetime
from bs4 import BeautifulSoup
import os
import google.generativeai as genai
import requests
import json
from datetime import datetime, timedelta
import google.ai.generativelanguage as glm
import re
from uuid import uuid4

app = Flask(__name__)

app.config['SECRET_KEY'] = 'a1b2c3d4e5f678901234567890abcdef'

CORS(app, supports_credentials=True)

YOUR_GEMINI_API_KEY = 'Buraya_kendi_gemini_api_key_girin' #Üzgünüm...
OPENWEATHER_API_KEY = 'Github_hatasi_sagdakini_yapistir' #9a939f5d0fe0209b89ae649eebf85d7c

genai.configure(api_key=YOUR_GEMINI_API_KEY)

try:
    model = joblib.load("hava_durumu_model.pkl")
    encoder = joblib.load("encoder.pkl")
    print("Modeller başarıyla yüklendi: hava_durumu_model.pkl, encoder.pkl")
except FileNotFoundError as e:
    print(f"HATA: Model dosyalarından biri bulunamadı: {e}")
    print(
        "Lütfen 'hava_durumu_model.pkl' ve 'encoder.pkl' dosyalarının uygulamanızla aynı dizinde olduğundan emin olun.")
    exit()


def get_weather_forecast_from_ml_model(city: str, date: str = None) -> dict:
    import re

    print(f"[DEBUG_ML] Fonksiyon çağrıldı - Şehir: {city}, Tarih: {date}")

    today = datetime.now()
    target_date = today

    city_for_model = city.strip().title()
    print(f"[DEBUG_ML] Normalize edilmiş şehir: {city_for_model}")

    if date:
        date_lower = date.lower().strip()
        print(f"[DEBUG_ML] İşlenecek tarih: {date_lower}")

        try:
            for date_format in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    target_date = datetime.strptime(date, date_format)
                    print(f"[DEBUG_ML] Tarih başarıyla çözüldü: {target_date}")
                    break
                except ValueError:
                    continue
            else:
                print(f"[UYARI_ML] Tarih formatı anlaşılamadı: {date}, bugün kullanılıyor")
                target_date = today
        except Exception as e:
            print(f"[HATA_ML] Tarih işleme hatası: {e}, bugün kullanılıyor")
            target_date = today
    else:
        target_date = today

    print(f"[DEBUG_ML] Hedef tarih (ML için): {target_date}")

    tarih_str_for_ml_model = target_date.strftime("%d-%m-%Y")
    gun = target_date.day
    ay = target_date.month
    hafta_gunu = target_date.weekday()

    try:
        print(f"[DEBUG_ML] Encoder'a gönderilen şehir: {city_for_model}")
        df_il = pd.DataFrame({"il": [city_for_model]})
        try:
            il_encoded = encoder.transform(df_il)
            il_df = pd.DataFrame(il_encoded, columns=encoder.get_feature_names_out())
            print(f"[DEBUG_ML] Şehir başarıyla encode edildi. il_df sütunları: {il_df.columns.tolist()}")
        except Exception as encode_error:
            print(f"[HATA_ML] Şehir encode hatası: {encode_error}")
            alternative_names = [
                city.upper(),
                city.lower(),
                city.title(),
                city.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace(
                    'ç', 'c')
            ]

            encoded_successfully = False
            for alt_name in alternative_names:
                try:
                    df_il_alt = pd.DataFrame({"il": [alt_name]})
                    il_encoded = encoder.transform(df_il_alt)
                    il_df = pd.DataFrame(il_encoded, columns=encoder.get_feature_names_out())
                    print(f"[DEBUG_ML] Alternatif şehir adı başarılı: {alt_name}")
                    encoded_successfully = True
                    break
                except:
                    continue

            if not encoded_successfully:
                return {
                    "error": f"'{city}' şehri ML modelinde bulunamadı. Lütfen geçerli bir Türkiye şehir adı girin.",
                    "available_cities": "İstanbul, Ankara, İzmir, Kastamonu, Antalya gibi şehirleri deneyebilirsiniz."
                }

        X_input = pd.DataFrame({
            "gun": [gun],
            "ay": [ay],
            "hafta_gunu": [hafta_gunu]
        })

        X_full = pd.concat([X_input, il_df], axis=1)
        print(f"[DEBUG_ML] Model input hazırlandı (X_full sütunları): {X_full.columns.tolist()}")
        print(f"[DEBUG_ML] Model input (X_full ilk satırı): {X_full.iloc[0].to_dict()}")

        preds = model.predict(X_full)[0]
        print(f"[DEBUG_ML] Model tahmini tamamlandı: {preds}")

        result = {
            "success": True,
            "tahmin_max_sicaklik": round(float(preds[0]), 1),
            "tahmin_min_sicaklik": round(float(preds[1]), 1),
            "tahmin_yagis": round(float(preds[2]), 1),
            "il": city_for_model,
            "tarih": tarih_str_for_ml_model,
            "tarih_readable": target_date.strftime("%d %B %Y, %A"),
            "gun_farki": (target_date - today).days
        }

        print(f"[DEBUG_ML] Başarılı sonuç: {result}")
        return result

    except Exception as e:
        error_msg = f"ML model tahmini yapılırken hata oluştu: {str(e)}"
        print(f"[HATA_ML_GENEL] {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "error": error_msg,
            "details": str(e)
        }
@app.route("/get_air_pollution", methods=["GET"])
def get_air_pollution():
    city = request.args.get("city")

    if not city:
        return jsonify({"error": "Şehir parametresi gerekli"}), 400

    try:
        print(f"[DEBUG] Hava kirliliği sorgusu - Şehir: {city}")

        api_key = "Sagdakini_yapis" #a1f28a3bdb8d1733a413ffd338fa166a

        geocoding_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city},TR&limit=1&appid={api_key}"

        geocoding_response = requests.get(geocoding_url, timeout=10)

        if geocoding_response.status_code != 200:
            return jsonify({"error": "Şehir koordinatları alınamadı"}), 500

        geocoding_data = geocoding_response.json()

        if not geocoding_data:
            return jsonify({"error": f"'{city}' şehri bulunamadı"}), 404

        latitude = geocoding_data[0]["lat"]
        longitude = geocoding_data[0]["lon"]
        city_name = geocoding_data[0]["name"]

        print(f"[DEBUG] Koordinatlar - Lat: {latitude}, Lon: {longitude}")

        air_pollution_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={latitude}&lon={longitude}&appid={api_key}"

        air_response = requests.get(air_pollution_url, timeout=10)

        if air_response.status_code != 200:
            return jsonify({"error": "Hava kirliliği verileri alınamadı"}), 500

        air_data = air_response.json()

        if "list" in air_data and len(air_data["list"]) > 0:
            current_air = air_data["list"][0]

            aqi = current_air["main"]["aqi"]

            # AQI açıklamaları
            aqi_descriptions = {
                1: {"text": "Çok İyi", "emoji": "🟢",
                    "advice": "Hava kalitesi mükemmel, dışarıda vakit geçirmek için ideal!"},
                2: {"text": "İyi", "emoji": "🟡", "advice": "Hava kalitesi iyi, normal aktiviteler yapabilirsin."},
                3: {"text": "Orta", "emoji": "🟠",
                    "advice": "Hassas kişiler dikkat etmeli, uzun süreli dış aktivitelerden kaçının."},
                4: {"text": "Kötü", "emoji": "🔴",
                    "advice": "Hava kalitesi kötü, dış aktiviteleri sınırla ve maske kullan."},
                5: {"text": "Çok Kötü", "emoji": "🟣", "advice": "Hava kalitesi tehlikeli! Dışarı çıkmayı en aza indir."}
            }

            aqi_info = aqi_descriptions.get(aqi, {"text": "Bilinmiyor", "emoji": "❓", "advice": "Veri alınamadı"})

            components = current_air.get("components", {})

            from datetime import datetime
            timestamp = current_air.get("dt", 0)
            measurement_time = datetime.fromtimestamp(timestamp).strftime(
                "%d/%m/%Y %H:%M") if timestamp else "Bilinmiyor"

            result = {
                "success": True,
                "city": city_name,
                "country": "Türkiye",
                "coordinates": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "air_quality": {
                    "aqi": aqi,
                    "aqi_text": aqi_info["text"],
                    "aqi_emoji": aqi_info["emoji"],
                    "advice": aqi_info["advice"]
                },
                "pollutants": {
                    "co": components.get("co", 0),
                    "no": components.get("no", 0),
                    "no2": components.get("no2", 0),
                    "o3": components.get("o3", 0),
                    "so2": components.get("so2", 0),
                    "pm2_5": components.get("pm2_5", 0),
                    "pm10": components.get("pm10", 0),
                    "nh3": components.get("nh3", 0)
                },
                "measurement_time": measurement_time,
                "source": "OpenWeatherMap Air Pollution API"
            }

            print(f"[DEBUG] Hava kirliliği sonucu: AQI={aqi}, Şehir={city_name}")

            return jsonify(result)

        else:
            return jsonify({"error": "Hava kirliliği verileri işlenemedi"}), 500

    except requests.exceptions.Timeout:
        return jsonify({"error": "API isteği zaman aşımına uğradı"}), 408
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API isteği başarısız: {str(e)}"}), 500
    except Exception as e:
        print(f"[HATA] Hava kirliliği hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Hava kirliliği verisi alınırken hata: {str(e)}"}), 500


@app.route("/get_earthquake_data", methods=["GET"])
def get_kandilli_earthquake_data():
    url = "http://www.koeri.boun.edu.tr/scripts/sondepremler.asp"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        response.encoding = 'iso-8859-9'
        soup = BeautifulSoup(response.text, 'html.parser')
        pre_tag = soup.find('pre')

        if not pre_tag:
            return {"error": "Deprem verileri bulunamadı (pre etiketi yok).", "earthquakes": []}

        lines = pre_tag.get_text().strip().split('\n')
        data_lines = lines[6:]
        earthquakes = []
        for line in data_lines:
            if not line.strip():
                continue

            try:
                parts = line.split()
                if len(parts) < 8:
                    continue
                date_time_str = f"{parts[0]} {parts[1]}"

                location_parts = parts[8:]
                location = " ".join(location_parts).strip()

                earthquake_info = {
                    "time": datetime.strptime(date_time_str, "%Y.%m.%d %H:%M:%S").isoformat(),
                    "latitude": float(parts[2]),
                    "longitude": float(parts[3]),
                    "depth": float(parts[4]),
                    "magnitude": float(parts[6]),
                    "location": location
                }
                earthquakes.append(earthquake_info)
            except (ValueError, IndexError) as e:
                print(f"Satır parse edilirken hata oluştu: {line} - Hata: {e}")
                continue

        return {"earthquakes": earthquakes}

    except requests.exceptions.RequestException as e:
        return {"error": f"Web sitesine bağlanırken hata oluştu: {e}", "earthquakes": []}
    except Exception as e:
        return {"error": f"Deprem verileri işlenirken beklenmeyen hata oluştu: {e}", "earthquakes": []}

# --- Konumdan Şehir Adı  ---
@app.route("/get_city_from_coords", methods=["POST"])
def get_city_from_coords():
    if not request.json:
        return jsonify({"error": "Geçersiz istek: JSON formatında veri bekleniyor."}), 400

    data = request.json
    lat = data.get("lat")
    lon = data.get("lon")

    if lat is None or lon is None:
        return jsonify({"error": "Enlem veya boylam bilgisi eksik."}), 400

    openweather_geocode_url = f"http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={OPENWEATHER_API_KEY}&lang=tr"
    try:
        response = requests.get(openweather_geocode_url, timeout=5)
        response.raise_for_status()
        geocode_data = response.json()
        if geocode_data and len(geocode_data) > 0:
            city_name = geocode_data[0].get("name")
            return jsonify({"city_name": city_name})
        else:
            return jsonify({"error": "Koordinatlar için şehir bulunamadı."}), 404
    except requests.exceptions.RequestException as e:
        print(f"Coğrafi kodlama API hatası: {e}")
        return jsonify({"error": f"Konumdan şehir alınamadı: {str(e)}", "detay": str(e)}), 500
    except Exception as e:
        print(f"Coğrafi kodlama işleme hatası: {e}")
        return jsonify({"error": f"Konumdan şehir işlenirken hata oluştu: {str(e)}", "detay": str(e)}), 500


# --- OpenWeatherMap API ---
@app.route("/get_weather_info", methods=["POST"])
def get_weather_info():
    if not request.json:
        return jsonify({"error": "Geçersiz istek: JSON formatında veri bekleniyor."}), 400

    data = request.json
    city = data.get("city")

    if not city:
        return jsonify({"error": "Şehir bilgisi eksik."}), 400

    openweather_api_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={OPENWEATHER_API_KEY}&lang=tr"
    try:
        owm_response = requests.get(openweather_api_url, timeout=10)
        owm_response.raise_for_status()
        owm_data = owm_response.json()
        if owm_data.get("cod") == "404":
            return jsonify({"error": f"Anlık hava durumu için '{city}' şehri bulunamadı."}), 404
        current_weather = {
            "temp": owm_data["main"]["temp"],
            "feels_like": owm_data["main"]["feels_like"],
            "humidity": owm_data["main"]["humidity"],
            "description": owm_data["weather"][0]["description"],
            "icon_id": owm_data["weather"][0]["id"],
            "city_name": owm_data["name"],
            "country": owm_data["sys"]["country"]
        }
    except requests.exceptions.RequestException as e:
        print(f"OpenWeatherMap API hatası: {e}")
        return jsonify({"error": f"Anlık hava durumu alınamadı: {str(e)}", "detay": str(e)}), 500
    except Exception as e:
        print(f"OpenWeatherMap işleme hatası: {e}")
        return jsonify({"error": f"Anlık hava durumu işlenirken hata oluştu: {str(e)}", "detay": str(e)}), 500

    session_id = str(uuid4())
    session['chat_history'] = []
    session['current_city'] = city

    return jsonify({"current_weather": current_weather, "session_id": session_id})

def _to_json_compatible(obj):
    if hasattr(obj, '_pb'):
        try:
            return _to_json_compatible(vars(obj._pb))
        except Exception:
            return str(obj)

    elif isinstance(obj, dict):
        return {k: _to_json_compatible(v) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [_to_json_compatible(elem) for elem in obj]

    elif isinstance(obj, (glm.Part, glm.FunctionCall, glm.FunctionResponse, glm.Content)):
        if hasattr(obj, 'text') and obj.text is not None:
            return {'text': obj.text}
        if hasattr(obj, 'function_call') and obj.function_call is not None:
            return {'function_call': _to_json_compatible(obj.function_call)}
        if hasattr(obj, 'function_response') and obj.function_response is not None:
            return {'function_response': _to_json_compatible(obj.function_response)}
        return {k: _to_json_compatible(v) for k, v in obj.__dict__.items() if not k.startswith('_')}

    elif hasattr(obj, '__dict__'):
        return {k: _to_json_compatible(v) for k, v in obj.__dict__.items() if not k.startswith('_')}

    else:
        return obj


def parse_prediction_command(command):
    try:
        import re
        from datetime import datetime

        command_clean = command.lower().replace("tahmin et", "").strip()

        if not command_clean:
            return {
                "success": False,
                "error": "Şehir ve tarih bilgisi eksik!"
            }

        print(f"[DEBUG] Parse edilecek: '{command_clean}'")

        date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
        date_match = re.search(date_pattern, command_clean)

        if not date_match:
            return {
                "success": False,
                "error": "Tarih formatı hatalı! DD/MM/YYYY formatında tarih yazın (örnek: 09/04/2025)"
            }
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3))

        try:
            target_date = datetime(year, month, day)
            detected_date = target_date.strftime("%d/%m/%Y")
            print(f"[DEBUG] Geçerli tarih: {detected_date}")
        except ValueError:
            return {
                "success": False,
                "error": f"Geçersiz tarih: {day}/{month}/{year}"
            }
        date_str = date_match.group(0)
        remaining_text = command_clean.replace(date_str, "").strip()

        detected_city = remaining_text.strip()

        if not detected_city:
            return {
                "success": False,
                "error": "Şehir adı eksik! Örnek: 'tahmin et ankara 01/01/2026'"
            }

        detected_city = detected_city.title()

        print(f"[DEBUG] Parse başarılı - Şehir: {detected_city}, Tarih: {detected_date}")

        return {
            "success": True,
            "city": detected_city,
            "date": detected_date
        }

    except Exception as e:
        print(f"[HATA] Parse hatası: {str(e)}")
        return {
            "success": False,
            "error": f"Komut parse edilirken hata: {str(e)}"
        }

# --- Kişisel Asistan + ML Tahmin Chat Endpoint ---
@app.route("/chat", methods=["POST"])
def chat():
    if not request.json:
        return jsonify({"error": "Geçersiz istek: JSON formatında veri bekleniyor."}), 400

    data = request.json
    user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "Mesaj boş olamaz."}), 400

    # Session kontrolü
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid4())
        session['session_id'] = session_id
        session['chat_history'] = []

    try:
        print(f"[DEBUG] Kullanıcı mesajı: {user_message}")
        
        # "Tahmin et" komutu kontrolü
        user_message_clean = user_message.strip()
        if user_message_clean.lower().startswith("tahmin et"):
            print(f"[DEBUG] Tahmin et komutu algılandı: {user_message}")

            prediction_result = parse_prediction_command(user_message_clean)
            
            if prediction_result["success"]:
                city = prediction_result["city"]
                date = prediction_result["date"]
                
                print(f"[DEBUG] Parse edilen - Şehir: {city}, Tarih: {date}")

                ml_result = get_weather_forecast_from_ml_model(city=city, date=date)
                
                print(f"[DEBUG] E.V.A Model Sonucu: {ml_result}")

                if "error" in ml_result:
                    gemini_response_text = (
                        f"❌ Tahmin Hatası\n\n"
                        f"Üzgünüm, {city} için hava durumu tahmini alınamadı:\n"
                        f"{ml_result.get('error', 'Bilinmeyen hata')}\n\n"
                        f"💡 Doğru format:\n"
                        f"• Tahmin et [Şehir] [DD/MM/YYYY]\n"
                        f"• Örnek: Tahmin et İstanbul 15/04/2025"
                    )
                else:
                    result = ml_result
                    max_temp = result['tahmin_max_sicaklik']
                    min_temp = result['tahmin_min_sicaklik']
                    yagis = result['tahmin_yagis']


                    gun_farki = result.get("gun_farki", 0)
                    if gun_farki == 0:
                        date_info = "bugün"
                    elif gun_farki == 1:
                        date_info = "yarın"
                    elif gun_farki == -1:
                        date_info = "dün"
                    else:
                        date_info = result.get("tarih_readable", result.get("tarih"))

                    # sonuç
                    gemini_response_text = (
                        f"🎯 E.V.A Tahmin Sonucu\n\n"
                        f"📍 Konum: {result['il']}\n"
                        f"📅 Tarih: {date_info}\n\n"
                        f"🌡️ En Yüksek: {max_temp}°C\n"
                        f"❄️ En Düşük: {min_temp}°C\n"
                        f"🌧️ Yağış: {yagis} mm\n\n"
                        f"📊 Özet: Sıcaklık {min_temp}°C ile {max_temp}°C arasında değişecek."
                    )

                    if yagis == 0:
                        gemini_response_text += " Yağış beklenmez. ☀️"
                    elif yagis <= 5:
                        gemini_response_text += f" Hafif yağış beklenir. 🌦️"
                    else:
                        gemini_response_text += f" Yağışlı bir gün olacak. ☔"

                    gemini_response_text += (
                        f"\n\n💡 Diğer tahminler için:\n"
                        f"• Tahmin et [Şehir] [DD/MM/YYYY] formatını kullan! E.V.A yardımına koşsun!\n"
                        f"• Örnek: \"Tahmin et Bursa 20/05/2025\""
                    )
            else:
                gemini_response_text = (
                    f"❌ Komut Formatı Hatası\n\n"
                    f"{prediction_result['error']}\n\n"
                    f"🔧 Doğru format:\n"
                    f"• Tahmin et [Şehir] [DD/MM/YYYY]\n\n"
                    f"✅ Örnek kullanımlar:\n"
                    f"• Tahmin et Ankara 09/04/2025\n"
                    f"• Tahmin et İstanbul 15/05/2025\n"
                    f"• Tahmin et Kastamonu 01/06/2025\n"
                    f"• Tahmin et Trabzon 25/12/2025"
                )

        else:

            print(f"[DEBUG] Normal asistan modu")
            

            chat_history_dicts = session.get('chat_history', [])
            reconstructed_chat_history = []

            for entry in chat_history_dicts:
                if 'parts' in entry and isinstance(entry['parts'], list):
                    glm_parts = []
                    for part_dict in entry['parts']:
                        if 'text' in part_dict:
                            glm_parts.append(glm.Part(text=part_dict['text']))
                    if glm_parts:
                        reconstructed_chat_history.append(glm.Content(parts=glm_parts, role=entry.get('role')))

            gemini_personal_assistant = genai.GenerativeModel(
                'gemini-2.0-flash',
                system_instruction="""Sen çok yardımcı, arkadaş canlısı ve samimi bir kişisel asistansın. 

GÖREVLERIN:
- Kullanıcının her türlü sorusuna doğal, sıcak ve dostça bir şekilde yanıt ver
- Bilgi verirken eğlenceli ve anlaşılır dil kullan
- Günlük konuşmalarda samimi ve rahat ol
- Espri yapmaktan çekinme
- Her zaman yardımcı olmaya çalış
- Türkçe emojiler kullanarak mesajlarını renklendirmeyi seviyorsun

HAVA DURUMU ÖZEL BİLGİ:
- Eğer kullanıcı hava durumu sorarsa, ona "Tahmin et [Şehir] [DD/MM/YYYY]" formatını öner
- Örnek: "Tahmin et İstanbul 15/04/2025" veya "Tahmin et Ankara 09/04/2025"
- Sadece tam tarih formatı kabul ediliyor (DD/MM/YYYY)

KONULAR:
- Genel bilgiler ve eğitim
- Günlük yaşam tavsiyeleri
- Teknoloji yardımı
- Hobiler ve eğlence
- Motivasyon ve kişisel gelişim
- Her türlü soru ve sohbet

STIL:
- Samimi ve dostça
- Emojiler kullan 
- Kısa ve öz ama etkili yanıtlar
- Türkçe dilbilgisi kurallarına uy
- Kullanıcıyı 'sen' diye hitap et"""
            )
            

            chat_session = gemini_personal_assistant.start_chat(history=reconstructed_chat_history)
            response_from_gemini = chat_session.send_message(user_message)


            if (response_from_gemini.candidates and
                response_from_gemini.candidates[0].content.parts and
                response_from_gemini.candidates[0].content.parts[0].text):
                gemini_response_text = response_from_gemini.candidates[0].content.parts[0].text
            else:
                gemini_response_text = "Üzgünüm, şu anda yanıt veremiyorum. Biraz sonra tekrar dener misin? 😅"

        print(f"[DEBUG] Final yanıt: {gemini_response_text}")

        chat_history_dicts = session.get('chat_history', [])
        chat_history_dicts.append({'role': 'user', 'parts': [{'text': user_message}]})
        chat_history_dicts.append({'role': 'model', 'parts': [{'text': gemini_response_text}]})
        session['chat_history'] = chat_history_dicts

        return jsonify({"gemini_response": gemini_response_text})

    except Exception as e:
        print(f"[HATA] Chat hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Sohbet işlenirken hata oluştu: {str(e)}"}), 500

@app.route("/chat_status", methods=["GET"])
def chat_status():
    try:
        session_id = session.get('session_id', 'Yok')
        chat_history_count = len(session.get('chat_history', []))
        
        return jsonify({
            "session_id": session_id,
            "message_count": chat_history_count,
            "status": "Aktif" if session_id != 'Yok' else "Pasif"
        })
    except Exception as e:
        return jsonify({"error": f"Durum kontrolü hatası: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
