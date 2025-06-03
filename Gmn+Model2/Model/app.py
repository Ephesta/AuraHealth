import joblib
import pandas as pd
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from bs4 import BeautifulSoup
import google.generativeai as genai
import requests
from datetime import datetime
import google.ai.generativelanguage as glm
import re
from uuid import uuid4
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a1b2c3d4e5f678901234567890abcdef'

CORS(app, supports_credentials=True,
     origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500", "http://127.0.0.1:5500"])

YOUR_GEMINI_API_KEY = 'AIzaSyCbZ4uXbamNFrUDlJJxsNiwuPxAQe7Khd8'
OPENWEATHER_API_KEY = '9a939f5d0fe0209b89ae649eebf85d7c'

genai.configure(api_key=YOUR_GEMINI_API_KEY)

try:
    model = joblib.load("hava_durumu_model.pkl")
    encoder = joblib.load("encoder.pkl")
except FileNotFoundError as e:
    print(f"HATA: Model dosyalarından biri bulunamadı: {e}")
    exit()


def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        radius = 6371
        distance = radius * c
        return round(distance, 2)
    except Exception:
        return float('inf')


def normalize_location_to_city(lat, lon):
    try:
        geocode_url = f"http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=5&appid={OPENWEATHER_API_KEY}&lang=tr"

        response = requests.get(geocode_url, timeout=5)
        response.raise_for_status()
        geocode_data = response.json()

        if not geocode_data:
            return {"error": "Konum bilgisi alınamadı"}

        normalized_city = None

        for location in geocode_data:
            name = location.get("name", "")
            state = location.get("state", "")
            country = location.get("country", "")

            if country != "TR":
                continue

            if state and state.strip():
                normalized_city = state.strip()
                break
            elif name and name.strip():
                normalized_city = name.strip()

        if not normalized_city:
            normalized_city = geocode_data[0].get("name", "İstanbul")

        normalized_city = normalized_city.title()

        return {
            "success": True,
            "original_location": geocode_data[0] if geocode_data else {},
            "normalized_city": normalized_city,
            "coordinates": {"lat": lat, "lon": lon}
        }

    except Exception as e:
        return {
            "error": f"Konum normalize edilemedi: {str(e)}",
            "fallback_city": "İstanbul"
        }


def get_city_coordinates(city_name):
    try:
        geocoding_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name},TR&limit=1&appid={OPENWEATHER_API_KEY}&lang=tr"

        response = requests.get(geocoding_url, timeout=5)
        response.raise_for_status()
        geocoding_data = response.json()

        if not geocoding_data:
            return {"error": f"'{city_name}' şehri bulunamadı"}

        location = geocoding_data[0]
        lat = location.get("lat")
        lon = location.get("lon")
        city_display_name = location.get("name", city_name)

        if lat is None or lon is None:
            return {"error": f"'{city_name}' için koordinat alınamadı"}

        return {
            "success": True,
            "city": city_display_name,
            "lat": lat,
            "lon": lon,
            "coordinates": {"lat": lat, "lon": lon}
        }

    except Exception as e:
        return {"error": f"Şehir koordinatları alınamadı: {str(e)}"}


def parse_earthquake_command(command):
    try:
        command_clean = command.lower().replace("deprem", "").strip()

        if not command_clean:
            return {
                "success": True,
                "use_user_location": True,
                "city": None
            }

        detected_city = command_clean.strip().title()

        return {
            "success": True,
            "use_user_location": False,
            "city": detected_city
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Komut parse hatası: {str(e)}"
        }


def get_kandilli_earthquake_data():
    url = "http://www.koeri.boun.edu.tr/scripts/sondepremler.asp"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'iso-8859-9'

        soup = BeautifulSoup(response.text, 'html.parser')
        pre_tag = soup.find('pre')

        if not pre_tag:
            return {"error": "Deprem verileri bulunamadı", "earthquakes": []}

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
            except (ValueError, IndexError):
                continue

        return {"earthquakes": earthquakes}

    except Exception as e:
        return {"error": f"Deprem verileri alınamadı: {e}", "earthquakes": []}


def get_nearest_earthquakes(user_lat, user_lon, limit=3):
    try:
        earthquake_data = get_kandilli_earthquake_data()

        if "error" in earthquake_data or not earthquake_data.get("earthquakes"):
            return {"error": "Deprem verileri alınamadı", "earthquakes": []}

        earthquakes = earthquake_data["earthquakes"]

        for earthquake in earthquakes:
            try:
                eq_lat = earthquake["latitude"]
                eq_lon = earthquake["longitude"]
                distance = calculate_distance(user_lat, user_lon, eq_lat, eq_lon)
                earthquake["distance_km"] = distance
            except Exception:
                earthquake["distance_km"] = float('inf')

        nearest_earthquakes = sorted(earthquakes, key=lambda x: x["distance_km"])[:limit]

        return {
            "success": True,
            "earthquakes": nearest_earthquakes,
            "user_location": {"lat": user_lat, "lon": user_lon}
        }

    except Exception as e:
        return {"error": f"En yakın depremler hesaplanamadı: {str(e)}", "earthquakes": []}


def get_weather_forecast_from_ml_model(city: str, date: str = None) -> dict:
    today = datetime.now()
    target_date = today
    city_for_model = city.strip().title()

    if date:
        try:
            for date_format in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    target_date = datetime.strptime(date, date_format)
                    break
                except ValueError:
                    continue
            else:
                target_date = today
        except:
            target_date = today

    tarih_str_for_ml_model = target_date.strftime("%d-%m-%Y")
    gun = target_date.day
    ay = target_date.month
    hafta_gunu = target_date.weekday()

    try:
        df_il = pd.DataFrame({"il": [city_for_model]})
        try:
            il_encoded = encoder.transform(df_il)
            il_df = pd.DataFrame(il_encoded, columns=encoder.get_feature_names_out())
        except Exception:
            return {
                "error": f"'{city}' şehri ML modelinde bulunamadı.",
                "available_cities": "İstanbul, Ankara, İzmir, Kastamonu gibi şehirleri deneyin."
            }

        X_input = pd.DataFrame({
            "gun": [gun],
            "ay": [ay],
            "hafta_gunu": [hafta_gunu]
        })

        X_full = pd.concat([X_input, il_df], axis=1)
        preds = model.predict(X_full)[0]

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

        return result

    except Exception as e:
        return {"error": f"ML model tahmini hatası: {str(e)}"}


def parse_prediction_command(command):
    try:
        command_clean = command.lower().replace("tahmin et", "").strip()

        if not command_clean:
            return {"success": False, "error": "Şehir ve tarih bilgisi eksik!"}

        date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
        date_match = re.search(date_pattern, command_clean)

        if not date_match:
            return {
                "success": False,
                "error": "Tarih formatı hatalı! DD/MM/YYYY formatında tarih yazın"
            }

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3))

        try:
            target_date = datetime(year, month, day)
            detected_date = target_date.strftime("%d/%m/%Y")
        except ValueError:
            return {"success": False, "error": f"Geçersiz tarih: {day}/{month}/{year}"}

        date_str = date_match.group(0)
        remaining_text = command_clean.replace(date_str, "").strip()
        detected_city = remaining_text.strip()

        if not detected_city:
            return {"success": False, "error": "Şehir adı eksik!"}

        detected_city = detected_city.title()

        return {
            "success": True,
            "city": detected_city,
            "date": detected_date
        }

    except Exception as e:
        return {"success": False, "error": f"Komut parse hatası: {str(e)}"}


@app.route("/normalize_location", methods=["POST"])
def normalize_location():
    if not request.json:
        return jsonify({"error": "JSON gerekli"}), 400

    data = request.json
    lat = data.get("lat")
    lon = data.get("lon")

    if lat is None or lon is None:
        return jsonify({"error": "Koordinat bilgisi eksik"}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return jsonify({"error": "Geçersiz koordinat formatı"}), 400

    result = normalize_location_to_city(lat, lon)
    return jsonify(result)


@app.route("/get_weather_info", methods=["POST"])
def get_weather_info():
    if not request.json:
        return jsonify({"error": "Geçersiz istek: JSON formatında veri bekleniyor."}), 400

    data = request.json
    city = data.get("city")
    user_lat = data.get("lat")
    user_lon = data.get("lon")

    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
        session['chat_history'] = []

    if user_lat is not None and user_lon is not None:
        try:
            session['user_latitude'] = float(user_lat)
            session['user_longitude'] = float(user_lon)

            if not city:
                location_result = normalize_location_to_city(float(user_lat), float(user_lon))
                if location_result.get("success"):
                    city = location_result.get("normalized_city", "İstanbul")
                else:
                    city = location_result.get("fallback_city", "İstanbul")
        except (ValueError, TypeError):
            pass

    if not city:
        return jsonify({"error": "Şehir bilgisi veya konum bilgisi eksik."}), 400

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
        return jsonify({"error": f"Anlık hava durumu alınamadı: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Anlık hava durumu işlenirken hata oluştu: {str(e)}"}), 500

    session['current_city'] = city

    return jsonify({
        "current_weather": current_weather,
        "session_id": session['session_id'],
        "normalized_city": city
    })


@app.route("/chat", methods=["POST"])
def chat():
    """Ana chat endpoint"""
    if not request.json:
        return jsonify({"error": "JSON gerekli"}), 400

    data = request.json
    user_message = data.get("message")
    user_lat = data.get("lat")
    user_lon = data.get("lon")

    if not user_message:
        return jsonify({"error": "Mesaj boş"}), 400

    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
        session['chat_history'] = []

    if user_lat is not None and user_lon is not None:
        session['user_latitude'] = float(user_lat)
        session['user_longitude'] = float(user_lon)

    try:
        user_message_clean = user_message.strip()

        if user_message_clean.lower() in ['!help', 'help', '?']:
            gemini_response_text = (
                "🤖 **E.V.A Asistan - Komut Listesi** 🤖\n\n"
                "🌦️ **Hava Durumu Tahmini:**\n"
                "• Tahmin et [Şehir] [DD/MM/YYYY]\n"
                "• Örnek: Tahmin et İstanbul 15/04/2025\n\n"
                "🏔️ **Deprem Sorgulama:**\n"
                "• deprem - Konumuna yakın depremleri gösterir 📍\n"
                "• deprem [Şehir] - O şehire yakın depremleri gösterir\n"
                "• Örnek: deprem Ankara, deprem İzmir\n\n"
                "❓ **Yardım:**\n"
                "• !help - Bu menüyü gösterir\n\n"
                "🚀 **Başlamak için bir komut dene!**"
            )

        elif user_message_clean.lower().startswith('deprem') or user_message_clean.lower() in ['yakın depremler',
                                                                                               'depremler']:
            earthquake_parse_result = parse_earthquake_command(user_message_clean)

            if not earthquake_parse_result["success"]:
                gemini_response_text = (
                    f"❌ **Deprem Komut Hatası**\n\n"
                    f"{earthquake_parse_result.get('error')}\n\n"
                    f"🔧 **Kullanım:**\n"
                    f"• deprem - Konumuna yakın depremler\n"
                    f"• deprem [Şehir] - O şehire yakın depremler\n\n"
                    f"📝 **Örnek:** deprem Ankara"
                )
            else:
                use_user_location = earthquake_parse_result["use_user_location"]
                target_city = earthquake_parse_result["city"]

                if use_user_location:
                    user_lat_final = session.get('user_latitude')
                    user_lon_final = session.get('user_longitude')
                    current_city = session.get('current_city')

                    if user_lat is not None:
                        user_lat_final = float(user_lat)
                        session['user_latitude'] = user_lat_final
                    if user_lon is not None:
                        user_lon_final = float(user_lon)
                        session['user_longitude'] = user_lon_final

                    if user_lat_final is None or user_lon_final is None:
                        gemini_response_text = (
                            "📍 **Konum Bilgisi Bulunamadı**\n\n"
                            "Konumun henüz tespit edilmemiş! 😅\n\n"
                            "🔧 Çözüm:\n"
                            "1. Konum izni ver\n"
                            "2. Hava durumu sorgula\n"
                            "3. Sonra deprem komutunu dene\n\n"
                            "💡 Alternatif: deprem [Şehir] yazabilirsin!\n"
                            "📝 Örnek: deprem İstanbul\n\n"
                            "❓ Yardım için !help yaz!"
                        )
                    else:
                        query_city_name = current_city or "Konumun"
                        nearest_eq_result = get_nearest_earthquakes(user_lat_final, user_lon_final, 3)
                else:
                    city_coord_result = get_city_coordinates(target_city)

                    if "error" in city_coord_result:
                        gemini_response_text = (
                            f"❌ Şehir Bulunamadı\n\n"
                            f"'{target_city}' şehri bulunamadı! 😅\n\n"
                            f"🔍 Hata:{city_coord_result.get('error')}\n\n"
                            f"💡 Öneriler:\n"
                            f"• Şehir adını kontrol et\n"
                            f"• Türkçe karakter kullan\n"
                            f"• Büyük şehirleri dene\n\n"
                            f"📝 Örnek: deprem Ankara, deprem İstanbul"
                        )
                    else:
                        user_lat_final = city_coord_result["lat"]
                        user_lon_final = city_coord_result["lon"]
                        query_city_name = city_coord_result["city"]
                        nearest_eq_result = get_nearest_earthquakes(user_lat_final, user_lon_final, 3)

                if 'nearest_eq_result' in locals():
                    if "error" in nearest_eq_result:
                        gemini_response_text = (
                            "❌ **Deprem Verisi Hatası**\n\n"
                            f"Depremler alınamadı: {nearest_eq_result.get('error')}\n\n"
                            "🔄 Biraz sonra tekrar dene!"
                        )
                    else:
                        earthquakes = nearest_eq_result["earthquakes"]

                        if not earthquakes:
                            gemini_response_text = (
                                f"🏔️ **Deprem Sorgusu** - {query_city_name}\n\n"
                                "📍 Yakın deprem bulunamadı.\n\n"
                                "✅ Bu iyi haber! Yakın zamanda deprem olmamış."
                            )
                        else:
                            location_info = f" - {query_city_name}"
                            gemini_response_text = f"🏔️ **En Yakın Depremler**{location_info}\n\n"

                            for i, eq in enumerate(earthquakes, 1):
                                try:
                                    eq_time = datetime.fromisoformat(eq["time"])
                                    time_str = eq_time.strftime("%d/%m/%Y %H:%M")

                                    now = datetime.now()
                                    time_diff = now - eq_time

                                    if time_diff.days > 0:
                                        time_ago = f"{time_diff.days} gün önce"
                                    elif time_diff.seconds > 3600:
                                        hours = time_diff.seconds // 3600
                                        time_ago = f"{hours} saat önce"
                                    elif time_diff.seconds > 60:
                                        minutes = time_diff.seconds // 60
                                        time_ago = f"{minutes} dakika önce"
                                    else:
                                        time_ago = "Az önce"
                                except:
                                    time_str = eq["time"]
                                    time_ago = ""

                                magnitude = eq["magnitude"]
                                if magnitude >= 5.0:
                                    mag_emoji = "🔴"
                                    mag_desc = "Kuvvetli"
                                elif magnitude >= 4.0:
                                    mag_emoji = "🟠"
                                    mag_desc = "Güçlü"
                                elif magnitude >= 3.0:
                                    mag_emoji = "🟡"
                                    mag_desc = "Orta"
                                else:
                                    mag_emoji = "🟢"
                                    mag_desc = "Hafif"

                                distance = eq['distance_km']
                                if distance < 50:
                                    distance_desc = "Çok Yakın"
                                elif distance < 100:
                                    distance_desc = "Yakın"
                                elif distance < 200:
                                    distance_desc = "Orta"
                                else:
                                    distance_desc = "Uzak"

                                gemini_response_text += (
                                    f"**{i}. Deprem** {mag_emoji} *({mag_desc})*\n"
                                    f"📊 Büyüklük: **{magnitude}** Richter\n"
                                    f"📏 Mesafe: **{distance} km** *({distance_desc})*\n"
                                    f"🕒 Zaman: {time_str}"
                                )

                                if time_ago:
                                    gemini_response_text += f" *({time_ago})*"

                                gemini_response_text += (
                                    f"\n🌍 Bölge: **{eq['location']}**\n"
                                    f"⬇️ Derinlik: {eq['depth']} km\n\n"
                                )

                            gemini_response_text += (
                                "📊 Skala: 🟢 Hafif | 🟡 Orta | 🟠 Güçlü | 🔴 Kuvvetli\n\n"
                                "🔄 Komutlar:\n"
                                "• deprem - Konumuna yakın\n"
                                "• deprem [Şehir] - O şehire yakın\n\n"
                                "❓ Yardım: !help"
                            )

        elif user_message_clean.lower().startswith("tahmin et"):
            prediction_result = parse_prediction_command(user_message_clean)

            if prediction_result["success"]:
                city = prediction_result["city"]
                date = prediction_result["date"]

                ml_result = get_weather_forecast_from_ml_model(city=city, date=date)

                if "error" in ml_result:
                    gemini_response_text = (
                        f"❌ Tahmin Hatası\n\n"
                        f"{ml_result.get('error')}\n\n"
                        f"💡 Format: Tahmin et [Şehir] [DD/MM/YYYY]\n"
                        f"📝 Örnek: Tahmin et İstanbul 15/04/2025"
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

                    gemini_response_text = (
                        f"🎯 E.V.A Tahmin Sonucu\n\n"
                        f"📍 Konum: {result['il']}\n"
                        f"📅 Tarih: {date_info}\n\n"
                        f"🌡️ En Yüksek: {max_temp}°C\n"
                        f"❄️ En Düşük: {min_temp}°C\n"
                        f"🌧️ Yağış: {yagis} mm\n\n"
                        f"📊 Sıcaklık {min_temp}°C - {max_temp}°C arasında."
                    )

                    if yagis == 0:
                        gemini_response_text += " Yağış yok ☀️"
                    elif yagis <= 5:
                        gemini_response_text += " Hafif yağış 🌦️"
                    else:
                        gemini_response_text += " Yağışlı ☔"

                    gemini_response_text += "\n\n💡 Başka tahmin: Tahmin et [Şehir] [DD/MM/YYYY]"
            else:
                gemini_response_text = (
                    f"❌ Format Hatası\n\n"
                    f"{prediction_result['error']}\n\n"
                    f"🔧 Doğru format: Tahmin et [Şehir] [DD/MM/YYYY]\n\n"
                    f"✅ Örnek: Tahmin et Ankara 09/04/2025"
                )

        else:
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
                system_instruction="""Sen yardımcı, arkadaş canlısı bir asistansın.

GÖREVLER:
- Samimi ve dostça yanıt ver
- Emojiler kullan
- Kısa ve etkili ol
- Türkçe konuş

KOMUTLAR:
- Hava durumu için: "Tahmin et [Şehir] [DD/MM/YYYY]"
- Deprem için: "deprem" veya "deprem [Şehir]"
- Yardım için: "!help"

Her türlü soruya yanıt ver, yardımcı ol!"""
            )

            chat_session = gemini_personal_assistant.start_chat(history=reconstructed_chat_history)
            response_from_gemini = chat_session.send_message(user_message)

            if (response_from_gemini.candidates and
                    response_from_gemini.candidates[0].content.parts and
                    response_from_gemini.candidates[0].content.parts[0].text):
                gemini_response_text = response_from_gemini.candidates[0].content.parts[0].text
            else:
                gemini_response_text = "Üzgünüm, yanıt veremiyorum 😅"

        chat_history_dicts = session.get('chat_history', [])
        chat_history_dicts.append({'role': 'user', 'parts': [{'text': user_message}]})
        chat_history_dicts.append({'role': 'model', 'parts': [{'text': gemini_response_text}]})
        session['chat_history'] = chat_history_dicts

        return jsonify({"gemini_response": gemini_response_text})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Chat hatası: {str(e)}"}), 500


@app.route("/get_air_pollution", methods=["GET"])
def get_air_pollution():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "Şehir gerekli"}), 400

    try:
        api_key = "a1f28a3bdb8d1733a413ffd338fa166a"
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

        air_pollution_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={latitude}&lon={longitude}&appid={api_key}"
        air_response = requests.get(air_pollution_url, timeout=10)

        if air_response.status_code != 200:
            return jsonify({"error": "Hava kirliliği alınamadı"}), 500

        air_data = air_response.json()
        if "list" in air_data and len(air_data["list"]) > 0:
            current_air = air_data["list"][0]
            aqi = current_air["main"]["aqi"]

            aqi_descriptions = {
                1: {"text": "Çok İyi", "emoji": "🟢", "advice": "Hava kalitesi mükemmel!"},
                2: {"text": "İyi", "emoji": "🟡", "advice": "Hava kalitesi iyi."},
                3: {"text": "Orta", "emoji": "🟠", "advice": "Hassas kişiler dikkat etmeli."},
                4: {"text": "Kötü", "emoji": "🔴", "advice": "Dış aktiviteleri sınırla."},
                5: {"text": "Çok Kötü", "emoji": "🟣", "advice": "Dışarı çıkmayı en aza indir!"}
            }

            aqi_info = aqi_descriptions.get(aqi, {"text": "Bilinmiyor", "emoji": "❓", "advice": "Veri yok"})
            components = current_air.get("components", {})

            timestamp = current_air.get("dt", 0)
            measurement_time = datetime.fromtimestamp(timestamp).strftime(
                "%d/%m/%Y %H:%M") if timestamp else "Bilinmiyor"

            result = {
                "success": True,
                "city": city_name,
                "country": "Türkiye",
                "coordinates": {"latitude": latitude, "longitude": longitude},
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
                "source": "OpenWeatherMap"
            }

            return jsonify(result)
        else:
            return jsonify({"error": "Hava kirliliği işlenemedi"}), 500

    except Exception as e:
        return jsonify({"error": f"Hava kirliliği hatası: {str(e)}"}), 500


@app.route("/get_city_from_coords", methods=["POST"])
def get_city_from_coords():
    if not request.json:
        return jsonify({"error": "JSON gerekli"}), 400

    data = request.json
    lat = data.get("lat")
    lon = data.get("lon")

    if lat is None or lon is None:
        return jsonify({"error": "Koordinat eksik"}), 400

    geocode_url = f"http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={OPENWEATHER_API_KEY}&lang=tr"

    try:
        response = requests.get(geocode_url, timeout=5)
        response.raise_for_status()
        geocode_data = response.json()

        if geocode_data and len(geocode_data) > 0:
            city_name = geocode_data[0].get("name")
            return jsonify({"city_name": city_name})
        else:
            return jsonify({"error": "Şehir bulunamadı"}), 404

    except Exception as e:
        return jsonify({"error": f"Şehir alınamadı: {str(e)}"}), 500


@app.route("/get_earthquake_data", methods=["GET"])
def get_earthquake_data():
    return jsonify(get_kandilli_earthquake_data())


@app.route("/chat_status", methods=["GET"])
def chat_status():
    try:
        return jsonify({
            "session_id": session.get('session_id', 'Yok'),
            "message_count": len(session.get('chat_history', [])),
            "status": "Aktif" if session.get('session_id') else "Pasif"
        })
    except Exception as e:
        return jsonify({"error": f"Durum hatası: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)