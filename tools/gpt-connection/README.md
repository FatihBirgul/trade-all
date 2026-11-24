# Trade AI GPT Bağlantı Testi

Trade AI'den bağımsız, Windows için yerel bir Sign in with ChatGPT doğrulama uygulamasıdır.

## Çalıştırma

Bu klasörde ilk kullanımda:

```powershell
npm install
npm run prepare-devkit
npm start
```

Sistem tarayıcısında açılan ekranda **ChatGPT ile giriş yap ve testi çalıştır** düğmesine basın. OpenAI sayfasında giriş yapın ve ChatGPT planı kullanımı iznini onaylayın. Uygulama, izin onaylanırsa otomatik olarak `Reply with exactly: Token sharing works.` mesajını yollar ve dönen yanıtı bire bir denetler.

Yönetici izni, API anahtarı veya ücretli bir servis gerekmez. `npm install` yalnızca uygulama klasörüne resmî DevKit'in gerekli Node bağımlılıklarını indirir.

## Güvenlik

OAuth belirteçleri `%APPDATA%\\Trade-AI-GPT-Baglanti-Testi` altında, Windows DPAPI ile mevcut Windows kullanıcısına bağlı şifreli biçimde saklanır. Uygulama şifre, tarayıcı çerezi veya OpenAI API anahtarı istemez ve bunları kaydetmez.

Kaynak temel: OpenAI'nin `sign-in-with-chatgpt-devkit` deposundaki `@siwc/local` SDK'sı.
