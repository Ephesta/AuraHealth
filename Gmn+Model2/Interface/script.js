// script.js

const wrapper = document.querySelector(".wrapper");
const infoTxt = wrapper.querySelector(".info-txt");
const airInfoTxt = wrapper.querySelector(".air-info-txt");
const earthquakeInfoTxt = wrapper.querySelector(".earthquake-info-txt");

// Header ve Arama Çubuğu Elementleri
const citySearchInput = document.querySelector("#citySearchInput");
const searchCityBtn = document.querySelector("#searchCityBtn");

// Panel Elementleri
const weatherPanel = wrapper.querySelector(".weather-panel");
const airPollutionPanel = wrapper.querySelector(".air-pollution-panel");
const earthquakePanel = wrapper.querySelector(".earthquake-panel");
const chatPanel = wrapper.querySelector(".chat-panel");

// Weather Panel İçindeki Elementler
const wIcon = weatherPanel.querySelector(".weather-icon");
const tempNumb = weatherPanel.querySelector(".temp .numb");
const weatherDescription = weatherPanel.querySelector(".weather-description");
const cityCountry = weatherPanel.querySelector(".location .city-country");
const feelsLikeNumb = weatherPanel.querySelector(".bottom-details .numb-2");
const humidityVal = weatherPanel.querySelector(".bottom-details .humidity-val");

// Air Pollution Panel Elementleri
const aqiValue = airPollutionPanel.querySelector(".aqi-value");
const aqiStatus = airPollutionPanel.querySelector(".aqi-status");
const airCityCountry = airPollutionPanel.querySelector(".air-city-country");
const pm25Val = airPollutionPanel.querySelector(".pm25-val");
const pm10Val = airPollutionPanel.querySelector(".pm10-val");
const o3Val = airPollutionPanel.querySelector(".o3-val");
const no2Val = airPollutionPanel.querySelector(".no2-val");
const aqiCircle = airPollutionPanel.querySelector(".aqi-circle");

// Earthquake Panel Elementleri
const earthquakeList = earthquakePanel.querySelector(".earthquake-list");
const last24hStat = document.querySelector("#last24h");
const lastWeekStat = document.querySelector("#lastWeek");

// Chat Panel Elementleri
const chatMessages = chatPanel.querySelector(".chat-messages");
const chatInput = chatPanel.querySelector("#chatInput");
const sendChatBtn = chatPanel.querySelector("#sendChatBtn");

// Alt Navigasyon Butonları
const showWeatherPanelBtn = document.querySelector("#showWeatherPanelBtn");
const showAirPolPanelBtn = document.querySelector("#showAirPolPanelBtn");
const showEqPanelBtn = document.querySelector("#showEqPanelBtn");
const showChatPanelBtn = document.querySelector("#showChatPanelBtn");

let currentCity = ""; // Global olarak mevcut şehri tutacağız
let currentCoords = null; // Mevcut koordinatları tutacağız
const DEFAULT_CITY = "Ankara"; // Konum izni verilmezse varsayılan şehir

// Backend API'mizin URL'si
const BACKEND_API_URL = "http://127.0.0.1:5000"; // Eğer 5000 dışında bir port kullanıyorsan değiştir

// --- Sayfa Yüklendiğinde Konum İzni Sorgula ---
window.addEventListener('load', () => {
    if (navigator.geolocation) {
        infoTxt.innerText = "Konumunuz alınıyor...";
        infoTxt.classList.add("pending");
        infoTxt.style.display = 'block';
        navigator.geolocation.getCurrentPosition(onSuccess, onError, {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        });
    } else {
        onError({ message: "Tarayıcınız konum servislerini desteklemiyor." });
        requestWeatherInfo(DEFAULT_CITY);
    }
});

// --- Event Listeners ---
citySearchInput.addEventListener("keyup", e => {
    if (e.key == "Enter" && citySearchInput.value.trim() !== "") {
        requestWeatherInfo(citySearchInput.value.trim());
    }
});

searchCityBtn.addEventListener("click", () => {
    const city = citySearchInput.value.trim();
    if (city !== "") {
        requestWeatherInfo(city);
    } else {
        infoTxt.innerText = "Lütfen bir şehir adı girin.";
        infoTxt.classList.add("error");
        infoTxt.style.display = 'block';
    }
});

showWeatherPanelBtn.addEventListener("click", () => showPanel('weather'));
citySearchInput.addEventListener("keyup", e => {
    if (e.key == "Enter" && citySearchInput.value.trim() !== "") {
        requestAirPollutionInfo(citySearchInput.value.trim());
    }
});

searchCityBtn.addEventListener("click", () => {
    const city = citySearchInput.value.trim();
    if (city !== "") {
        requestAirPollutionInfo(city);
    } else {
        infoTxt.innerText = "Lütfen bir şehir adı girin.";
        infoTxt.classList.add("error");
        infoTxt.style.display = 'block';
    }
});

showAirPolPanelBtn.addEventListener("click", () => {
    showPanel('air-pollution');
    // Eğer koordinatlar mevcutsa, hava kirliliği bilgisini tekrar iste
    if (currentCoords) {
        requestAirPollutionInfo(currentCity); // Mevcut şehri kullanarak iste
    }
});
showEqPanelBtn.addEventListener("click", () => {
    showPanel('earthquake');
    requestEarthquakeInfo();
});
showChatPanelBtn.addEventListener("click", () => showPanel('chat'));

// --- Konum Fonksiyonları ---
function onSuccess(position) {
    const { latitude, longitude } = position.coords;
    currentCoords = { lat: latitude, lon: longitude };
    
    fetch(`${BACKEND_API_URL}/get_city_from_coords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: latitude, lon: longitude })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            console.error("Geocoding API hatası:", data.error);
            infoTxt.innerText = `Konumdan şehir alınamadı: ${data.error}. ${DEFAULT_CITY} gösteriliyor.`;
            infoTxt.classList.replace("pending", "error");
            requestWeatherInfo(DEFAULT_CITY);
        } else {
            citySearchInput.value = data.city_name;
            requestWeatherInfo(data.city_name);
        }
    })
    .catch(error => {
        console.error("Geocoding fetch error:", error);
        infoTxt.innerText = `Konumdan şehir alınırken bağlantı hatası: ${error.message}. ${DEFAULT_CITY} gösteriliyor.`;
        infoTxt.classList.replace("pending", "error");
        requestWeatherInfo(DEFAULT_CITY);
    });
}

function onError(error) {
    console.error("Konum hatası:", error);
    infoTxt.innerText = `Konum izni reddedildi veya hata oluştu: ${error.message}. ${DEFAULT_CITY} gösteriliyor.`;
    infoTxt.classList.add("error");
    infoTxt.style.display = 'block';
    requestWeatherInfo(DEFAULT_CITY);
}

function requestAirPollutionInfo(city) {
    infoTxt.innerText = "Hava kirliliği bilgileri getiriliyor...";
    infoTxt.classList.remove("error");
    infoTxt.classList.add("pending");
    infoTxt.style.display = 'block';

    fetch(`${BACKEND_API_URL}/get_air_pollution?city=${encodeURIComponent(city)}`) // GET isteği için city parametresi
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            infoTxt.classList.replace("pending", "error");
            infoTxt.innerText = data.error;
            currentCity = ""; // Şehir bulunamadıysa mevcut şehri sıfırla
            airPollutionDetails({}); // Paneli temizle
        } else {
            airPollutionDetails(data); // Hava kirliliği detaylarını göster
            currentCity = data.city; // Mevcut şehri global değişkene ata
            citySearchInput.value = currentCity; // Arama çubuğunu güncel şehirle doldur

            infoTxt.classList.remove("pending", "error");
            infoTxt.style.display = 'none'; // Bilgi mesajını gizle

            showPanel('air-pollution'); // Hava kirliliği panelini göster
        }
    })
    .catch(error => {
        infoTxt.classList.replace("pending", "error");
        infoTxt.innerText = `Bağlantı hatası: ${error.message}. Sunucu çalışıyor mu?`;
        infoTxt.style.display = 'block';
        console.error("Fetch error:", error);
        currentCity = ""; // Hata durumunda şehri sıfırla
        airPollutionDetails({}); // Paneli temizle
    });
}

function airPollutionDetails(info) {
    // Bilgi yoksa veya hata varsa paneli temizle
    if (!info || !info.air_quality) {
        aqiValue.innerText = "N/A";
        aqiStatus.innerText = "Veri Yok";
        airCityCountry.innerText = "Şehir Bilinmiyor";
        pm25Val.innerText = "N/A";
        pm10Val.innerText = "N/A";
        o3Val.innerText = "N/A";
        no2Val.innerText = "N/A";
        aqiCircle.style.backgroundColor = "#ccc"; // Varsayılan renk
        return;
    }

    aqiValue.innerText = info.air_quality.aqi;
    aqiStatus.innerText = `${info.air_quality.aqi_text} ${info.air_quality.aqi_emoji}`;
    airCityCountry.innerText = `${info.city}, ${info.country}`;
    pm25Val.innerText = info.pollutants.pm2_5;
    pm10Val.innerText = info.pollutants.pm10;
    o3Val.innerText = info.pollutants.o3;
    no2Val.innerText = info.pollutants.no2;

    // AQI değerine göre renk ayarla
    const aqi = info.air_quality.aqi;
    if (aqi === 1) {
        aqiCircle.style.backgroundColor = "#00e400"; // Çok İyi (Yeşil)
    } else if (aqi === 2) {
        aqiCircle.style.backgroundColor = "#ffff00"; // İyi (Sarı)
    } else if (aqi === 3) {
        aqiCircle.style.backgroundColor = "#ff7e00"; // Orta (Turuncu)
    } else if (aqi === 4) {
        aqiCircle.style.backgroundColor = "#ff0000"; // Kötü (Kırmızı)
    } else if (aqi === 5) {
        aqiCircle.style.backgroundColor = "#8f3f97"; // Çok Kötü (Mor)
    } else {
        aqiCircle.style.backgroundColor = "#ccc"; // Bilinmiyor
    }
}

// --- Deprem Bilgisi Getirme ---
function requestEarthquakeInfo() {
    infoTxt.innerText = "Deprem bilgileri getiriliyor...";
    infoTxt.classList.remove("error");
    infoTxt.classList.add("pending");
    infoTxt.style.display = 'block';

    // Backend'deki deprem verisi endpoint'ine istek at
    fetch(`${BACKEND_API_URL}/get_earthquake_data`) // Bu endpoint'in app.py'de tanımlı olması gerekiyor
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            infoTxt.classList.replace("pending", "error");
            infoTxt.innerText = data.error;
            earthquakeDetails([]); // Paneli temizle
        } else {
            earthquakeDetails(data); // Deprem detaylarını göster
            infoTxt.classList.remove("pending", "error");
            infoTxt.style.display = 'none'; // Bilgi mesajını gizle
            showPanel('earthquake'); // Deprem panelini göster
        }
    })
    .catch(error => {
        infoTxt.classList.replace("pending", "error");
        infoTxt.innerText = `Bağlantı hatası: ${error.message}. Sunucu çalışıyor mu?`;
        infoTxt.style.display = 'block';
        console.error("Earthquake fetch error:", error);
        earthquakeDetails([]); // Paneli temizle
    });
}

function earthquakeDetails(data) {
    earthquakeList.innerHTML = ''; // Listeyi temizle
    let count24h = 0;
    let countWeek = 0;
    const now = new Date();
    const oneDayAgo = new Date(now.getTime() - (24 * 60 * 60 * 1000));
    const oneWeekAgo = new Date(now.getTime() - (7 * 24 * 60 * 60 * 1000));

    if (!data || !data.earthquakes || data.earthquakes.length === 0) {
        const noData = document.createElement("li");
        noData.classList.add("earthquake-item");
        noData.innerText = "Deprem verisi bulunamadı.";
        earthquakeList.appendChild(noData);
        last24hStat.innerText = "Son 24 saat: 0";
        lastWeekStat.innerText = "Son 1 hafta: 0";
        return;
    }

    data.earthquakes.forEach(eq => {
        const eqTime = new Date(eq.time); // Backend'den gelen zaman formatına göre ayarla
        if (eqTime > oneDayAgo) {
            count24h++;
        }
        if (eqTime > oneWeekAgo) {
            countWeek++;
        }

        const listItem = document.createElement("li");
        listItem.classList.add("earthquake-item");
        listItem.innerHTML = `
            <strong>Büyüklük: ${eq.magnitude}</strong> <br>
            Yer: ${eq.location} <br>
            Derinlik: ${eq.depth} km <br>
            Zaman: ${new Date(eq.time).toLocaleString('tr-TR')}
        `;
        earthquakeList.appendChild(listItem);
    });

    last24hStat.innerText = `Son 24 saat: ${count24h}`;
    lastWeekStat.innerText = `Son 1 hafta: ${countWeek}`;
}
// --- Hava Durumu Bilgisi Getirme ---
function requestWeatherInfo(city) {
    infoTxt.innerText = "Hava durumu bilgileri getiriliyor...";
    infoTxt.classList.remove("error");
    infoTxt.classList.add("pending");
    infoTxt.style.display = 'block';

    fetch(`${BACKEND_API_URL}/get_weather_info`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city: city })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            infoTxt.classList.replace("pending", "error");
            infoTxt.innerText = data.error;
            currentCity = ""; // Şehir bulunamadıysa mevcut şehri sıfırla
            chatMessages.innerHTML = ''; // Sohbeti temizle
            addBotMessage("Üzgünüm, hava durumu bilgisi bulunamıyor. Lütfen başka bir şehir deneyin.");
        } else {
            weatherDetails(data.current_weather);
            currentCity = data.current_weather.city_name; // Mevcut şehri global değişkene ata
            citySearchInput.value = currentCity; // Arama çubuğunu güncel şehirle doldur

            infoTxt.classList.remove("pending", "error");
            infoTxt.style.display = 'none'; // Bilgi mesajını gizle

            showPanel('weather'); // Hava durumu panelini göster
            
            // Chat geçmişini temizle ve ilk mesajı ekle (eğer farklı bir şehire geçildi ise)
            // Ya da sadece ilk kez yüklendiğinde hoşgeldin mesajı göster
            if (chatMessages.children.length === 0 || currentCity !== data.current_weather.city_name) {
                chatMessages.innerHTML = ''; // Sohbeti temizle
                addBotMessage(`Merhaba! Ben senin kişisel asistanınım.Istersen sohbet edelim,istersen dertleşelim.`);
                addBotMessage(`Bu arada harika bir haberim var! E.V.A yani Ephesta's Virtual Assistant çıktı`);
                addBotMessage(`E.V.A ile geleceğe yönelik hava durumu tahmini yapabilirsin ama hatırlatmakta fayda var gelecek ne kadar uzaksa doğruluk oranı o kadar düşük olur`);
                addBotMessage(`Hemen kullanmak için Tahmin et [Şehir] [DD/MM/YYYY] yaz !`);
            }
        }
    })
    .catch(error => {
        infoTxt.classList.replace("pending", "error");
        infoTxt.innerText = `Bağlantı hatası: ${error.message}. Sunucu çalışıyor mu?`;
        infoTxt.style.display = 'block';
        console.error("Fetch error:", error);
        currentCity = ""; // Hata durumunda şehri sıfırla
        chatMessages.innerHTML = ''; // Sohbeti temizle
        addBotMessage("Sunucuya bağlanılamadı. Lütfen sunucunun çalıştığından emin olun.");
    });
}

function weatherDetails(info) {
    tempNumb.innerText = Math.floor(info.temp);
    weatherDescription.innerText = info.description;
    cityCountry.innerText = `${info.city_name}, ${info.country}`;
    feelsLikeNumb.innerText = Math.floor(info.feels_like);
    humidityVal.innerText = `${info.humidity}%`;

    // İkon mantığı
    const id = info.icon_id;
    if (id == 800) { wIcon.src = "icons/clear.svg"; }
    else if (id >= 200 && id <= 232) { wIcon.src = "icons/storm.svg"; }
    else if (id >= 600 && id <= 622) { wIcon.src = "icons/snow.svg"; }
    else if (id >= 701 && id <= 781) { wIcon.src = "icons/haze.svg"; }
    else if (id >= 801 && id <= 804) { wIcon.src = "icons/cloud.svg"; }
    else if ((id >= 300 && id <= 321) || (id >= 500 && id <= 531)) { wIcon.src = "icons/rain.svg"; }
    else { wIcon.src = "icons/cloud.svg"; } // Varsayılan bir ikon
}

// --- Panel Yönetimi Fonksiyonu ---
function showPanel(panelName) {
    // Tüm panelleri gizle
    weatherPanel.classList.remove("active-panel");
    chatPanel.classList.remove("active-panel");
    wrapper.classList.remove("weather-active", "chat-active");
    airPollutionPanel.classList.remove("active-panel");
    wrapper.classList.remove("air-pollution-active");
    earthquakePanel.classList.remove("active-panel"); // Deprem paneli gizlendi

    // Tüm navigasyon butonlarının aktif stilini kaldır
    showWeatherPanelBtn.classList.remove("active-nav-btn");
    showChatPanelBtn.classList.remove("active-nav-btn");
    showAirPolPanelBtn.classList.remove("active-nav-btn");
    showEqPanelBtn.classList.remove("active-nav-btn");

    if (panelName === 'weather') {
        weatherPanel.classList.add("active-panel");
        wrapper.classList.add("weather-active");
        showWeatherPanelBtn.classList.add("active-nav-btn");
    } else if (panelName === 'chat') {
        chatPanel.classList.add("active-panel");
        wrapper.classList.add("chat-active");
        showChatPanelBtn.classList.add("active-nav-btn");
    }
    if (panelName === 'air-pollution') {
        airPollutionPanel.classList.add("active-panel");
        wrapper.classList.add("air-pollution-active");
        showAirPolPanelBtn.classList.add("active-nav-btn");
    }
    else if (panelName === 'earthquake') { // Deprem paneli eklendi
        earthquakePanel.classList.add("active-panel");
        wrapper.classList.add("earthquake-active");
        showEqPanelBtn.classList.add("active-nav-btn");
    }
}


// --- Chat Etkileşimleri ---
sendChatBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keyup", e => {
    if (e.key === "Enter") {
        sendMessage();
    }
});

function sendMessage() {
    const userMessage = chatInput.value.trim();
    if (userMessage === "") return;
    addUserMessage(userMessage);
    chatInput.value = ""; // Input'u temizle

    getGeminiResponse(userMessage, currentCity);
}

function addUserMessage(message) {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "user-message");
    messageDiv.innerText = message;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight; // En alta kaydır
}

function addBotMessage(message) {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "bot-message");
    messageDiv.innerText = message;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight; // En alta kaydır
}

async function getGeminiResponse(userMessage, city) {
    addBotMessage("Asistan yazıyor..."); // "Asistan yazıyor..." mesajı göster

    try {
        const response = await fetch(`${BACKEND_API_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userMessage, city: city })
        });
        const data = await response.json();

        // "Asistan yazıyor..." mesajını kaldır
        const lastBotMessage = chatMessages.querySelector(".bot-message:last-child");
        if (lastBotMessage && lastBotMessage.innerText === "Asistan yazıyor...") {
            chatMessages.removeChild(lastBotMessage);
        }

        if (data.error) {
            addBotMessage("Üzgünüm, isteğinizi işlerken bir hata oluştu: " + data.error);
        } else {
            addBotMessage(data.gemini_response);
        }
    } catch (error) {
        const lastBotMessage = chatMessages.querySelector(".bot-message:last-child");
        if (lastBotMessage && lastBotMessage.innerText === "Asistan yazıyor...") {
            chatMessages.removeChild(lastBotMessage);
        }
        addBotMessage("Bağlantı hatası: Sunucuya ulaşılamadı veya bir sorun oluştu.");
        console.error("Chat fetch error:", error);
    }
}