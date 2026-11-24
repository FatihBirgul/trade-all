# İlk mimari planı (tarihsel)

Güncel uygulama Expo Router kullanır. Aşağıdaki ilk planın test durumu güncel değildir; doğrulama için `VALIDATION.md`, gateway sınırları için `GATEWAY.md` esas alınmalıdır. Mevcut backend kullanıcı oturumu/JWT uçları sunmaz. Mobil HTTPS gateway ayrı ve henüz uygulanmamış bir bileşendir; backend bearer sırrı yalnız sunucuda kalmalıdır.

## Sınırlar

```
trade-ai-android (bu repo) ── HTTPS + kullanıcı JWT ──> trade-ai API /api/v2
                                                    └──> trade-ai-v2 (ayrı backend kodu)
```

- Mobil uygulama hiçbir backend kaynak kodunu değiştirmez.
- Her API isteği, varsa SecureStore'dan alınan kısa ömürlü kullanıcı oturum belirteci ile gönderilir.
- Borsa API anahtarları ve yönetici sırları yalnızca backend tarafında kalır.
- Canlı mod yalnızca görünür bir durumdur; emir gönderme çağrısı bu başlangıç sürümünde yoktur.

## Ekran rotası

1. Ana Sayfa — demo bakiye, sinyaller, günlük özet
2. Analiz — piyasa rejimi ve strateji özeti
3. Portföyler — demo portföy / canlı görünüm ayrımı
4. Tarayıcı — gelecekteki filtre ve alarm noktası
5. Ayarlar — tema, güvenlik ve sürüm bilgileri

## Doğrulama sırası

1. Expo bağımlılıklarını kilitle ve `npm run typecheck` çalıştır.
2. Android emülatör veya fiziksel cihazda Expo geliştirme derlemesini aç.
3. Demo API sözleşmesini test sunucusunda bağla.
4. Kimlik doğrulama, token yenileme ve hata durumlarını test et.
5. Ancak ondan sonra, sunucu tarafında izin verilirse salt-okunur canlı görünümü bağla.

> Bu aşamaların hiçbiri henüz uygulanmış test sonucu değildir.
