# HTTP Endpoint Check

Bir uç nokta listesinin beklenen HTTP durumunu verip vermediğini ölçer. Örneğin sağlık kontrolünde `200`, taşınmış bir sayfada `301` veya erişime kapalı bir rotada `403` bekleyebilirsin.

## Hızlı deneme

Python 3.10 veya üstüyle depo klasöründe bir terminalden örnek sunucuyu başlat.

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

İkinci terminalde denetimi çalıştır.

```powershell
python http_endpoint_check.py endpoints.example.json
python http_endpoint_check.py endpoints.example.json --json
```

Kendi uç noktaların için örnek dosyayı `endpoints.local.json` adıyla kopyala ve listedeki adresleri düzenle. Her öğeye bir `name`, `url` ve kabul edilen durum kodları dizisi olan `expect` ekle. `method` varsayılan olarak `GET` olur ve `HEAD` seçilebilir. `max_latency_ms` ile uç noktaya bir süre sınırı, `timeout_seconds` ile bağlantı ve okuma zaman aşımı koyabilirsin.

Ölçüm yanıt başlıkları gelene kadar sürer. Gövde indirilmez ve yönlendirme takip edilmez. HTTPS sertifikaları Python'un varsayılan doğrulamasıyla kontrol edilir. Sistem proxy ayarları geçerli olabilir.

Çıkış kodu `0` tüm kontrollerin geçtiğini, `1` en az bir uç noktanın başarısız olduğunu, `2` yapılandırma veya kullanım hatasını gösterir.

## Test

```powershell
python -m unittest -v
```

Testler geçici bir yerel HTTP sunucusu kullanır.
