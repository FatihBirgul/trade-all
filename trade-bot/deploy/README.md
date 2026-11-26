# Trade Bot — sunucu kurulumu ve dağıtım

Bu adımlar **bir kez** yapılır. Sonrasında `main` dalına yapılan her push, testler geçerse botu
sunucuda kendiliğinden günceller ve yeniden başlatır.

## Hızlı kurulum: tek komut

Sunucuya `root` olarak bağlanın, aşağıdaki satırı yapıştırıp Enter'a basın:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/FatihBirgul/trade-all/main/trade-bot/deploy/bootstrap.sh)
```

Betik sırayla şunları yapar:

1. Kurulumu yapar (aşağıdaki 1. adımın aynısı).
2. Dört Exness değerini tek tek sorar. Yapıştırdığınız değer güvenlik için ekranda görünmez; yapıştırıp Enter'a basın. Değerler `/etc/tradebot/tradebot.env` dosyasına yazılır (yalnızca servis okuyabilir).
3. Dağıtım için SSH anahtarı üretir.
4. Telefon erişimi için HTTPS'i kurar: `https://<IP>.sslip.io` (Caddy + Let's Encrypt; alan adı gerekmez).
5. GitHub'a eklemeniz gereken dört secret'ı (`VPS_HOST`, `VPS_USER`, `VPS_KNOWN_HOSTS`, `VPS_SSH_KEY`) ekrana yazar. Özel anahtar en sonda, ayrı bir blokta gösterilir; onu yalnızca GitHub Secret olarak yapıştırın.
6. Salt-okuma API keşfini çalıştırır ve sonucu `/root/tradebot-kesif.zip` olarak kaydeder.
7. Botu **dry-run** kipinde başlatır (gerçek emir göndermez).

Betiği yeniden çalıştırmak güvenlidir; daha önce girdiğiniz değerleri korur.

Aşağıdaki bölümler aynı adımların elle yapılışını anlatır; tek komutu kullandıysanız yalnızca 4. bölümdeki
GitHub Secrets ekranına ihtiyacınız var.

---

Komutlardaki `SUNUCU_IP` yerine Contabo sunucunuzun IP adresini yazın.

## 1. Sunucuda kurulum betiğini çalıştırın

Sunucuya `root` olarak bağlanın ve şunu çalıştırın:

```bash
curl -fsSL https://raw.githubusercontent.com/FatihBirgul/trade-all/main/trade-bot/deploy/install.sh -o install.sh
```

```bash
sudo bash install.sh
```

Repo gizliyse (private) `curl` çalışmaz. O durumda önce 5. bölümdeki "Gizli repo" adımını yapın.

Betik şunları kurar: `tradebot` servis kullanıcısı, `deploy` dağıtım kullanıcısı, `/opt/tradebot`
(kod + Python ortamı), `/var/lib/tradebot` (veritabanı), `/etc/tradebot/tradebot.env` (sırlar, izin 600),
`tradebot` systemd servisi ve saat eşitleme (NTP). Tekrar çalıştırmak güvenlidir.

## 2. Sırları doldurun

```bash
sudo nano /etc/tradebot/tradebot.env
```

| Değişken | Nereden alınır |
|---|---|
| `EXNESS_API_KEY` | Exness Personal Area → Key Management → API anahtarının kimliği |
| `EXNESS_PRIVATE_KEY` | Anahtar oluşturulurken verilen özel anahtar (128 hex karakter) |
| `EXNESS_ACCOUNT_ID` | Cent hesabınızın numarası |
| `EXNESS_GATEWAY_HOST` | Key Management'taki DNS kutusunda görünen host |

Bu dosya yalnızca sunucuda durur. İçeriğini kimseyle paylaşmayın, sohbete yapıştırmayın, repoya koymayın.

API anahtarında IP kısıtı açıksa sunucunun IP adresini izinli listeye ekleyin.

## 3. Dağıtım için SSH anahtarı oluşturun

Sunucuda, `deploy` kullanıcısı için bir anahtar çifti üretin:

```bash
sudo -u deploy bash -c 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && ssh-keygen -t ed25519 -N "" -f ~/.ssh/github_deploy -C github-deploy && cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

Özel anahtarı ekrana yazdırın ve tamamını kopyalayın (`-----BEGIN` satırından `-----END` satırına kadar):

```bash
sudo cat /home/deploy/.ssh/github_deploy
```

Sunucunun kimlik satırlarını da alın (GitHub'ın doğru sunucuya bağlandığını doğrulaması için):

```bash
ssh-keyscan SUNUCU_IP
```

## 4. GitHub Secrets ekleyin

GitHub'da repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Değer |
|---|---|
| `VPS_HOST` | Sunucu IP adresi |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | 3. adımda kopyaladığınız özel anahtarın tamamı |
| `VPS_KNOWN_HOSTS` | `ssh-keyscan` çıktısının tamamı (önerilir) |
| `VPS_PORT` | Yalnızca SSH portu 22 değilse |

İş akışı `production` ortamını kullanır. İsterseniz **Settings → Environments → production** altında
"Required reviewers" açarak her dağıtımı elle onaylayabilirsiniz.

Özel anahtarı GitHub'a ekledikten sonra sunucudaki kopyasını silebilirsiniz:

```bash
sudo rm /home/deploy/.ssh/github_deploy
```

## 5. Gizli repo (yalnızca repo private ise)

Sunucunun kodu çekebilmesi için salt-okuma bir "deploy key" gerekir:

```bash
sudo useradd --create-home --shell /bin/bash deploy 2>/dev/null; sudo -u deploy bash -c 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -C trade-all-readonly && cat ~/.ssh/id_ed25519.pub'
```

Çıkan `ssh-ed25519 ...` satırını GitHub'da repo → **Settings → Deploy keys → Add deploy key** ile ekleyin
("Allow write access" **işaretlenmez**). Ardından kurulum betiğini SSH adresiyle çalıştırın
(betiği bilgisayarınızdan `scp` ile kopyalayabilir ya da içeriğini `nano install.sh` ile yapıştırabilirsiniz):

```bash
sudo REPO_URL=git@github.com:FatihBirgul/trade-all.git bash install.sh
```

## 6. Kontrol

```bash
sudo systemctl status tradebot --no-pager
```

```bash
sudo journalctl -u tradebot -n 50 --no-pager
```

## API keşif betiği (ilk canlı adım)

Salt-okuma çalışır, emir göndermez. Hesap, limitler, enstrümanlar ve örnek mumları okuyup JSON olarak kaydeder:

```bash
sudo -u tradebot bash -c 'set -a; . /etc/tradebot/tradebot.env; set +a; cd /opt/tradebot/trade-bot && /opt/tradebot/.venv/bin/python -m tradebot.discover'
```

Betik sonunda çıktı klasörünün ve zip dosyasının yolunu yazar. Çıktıda API anahtarı ya da imza bulunmaz.

## Telefon uygulamasını bağlama

Sunucu adresi kurulum sonunda ekrana yazılır (`https://<IP>.sslip.io`; daha sonra `cat /etc/tradebot/public-url` ile
görebilirsiniz). Eşleştirme kodu için sunucuda:

```bash
tradebot-pair
```

Kod 10 dakika geçerlidir ve bir kez kullanılır. Uygulamada **Ayarlar → Bağlantı ayarları** ekranına adresi ve kodu girin.
API internete açıktır ama `/health` dışındaki her istek telefonunuza verilen gizli anahtarı (token) ister;
eşleştirme kodu 5 hatalı denemede iptal olur.

HTTPS'i yeniden kurmak gerekirse:

```bash
bash /opt/tradebot/trade-bot/deploy/setup-https.sh
```

## Telefon kaybolursa: tüm cihazların erişimini iptal etme

```bash
sudo -u tradebot bash -c 'set -a; . /etc/tradebot/tradebot.env; set +a; cd /opt/tradebot/trade-bot && /opt/tradebot/.venv/bin/python -m tradebot revoke'
```

Sonra yeni bir eşleştirme kodu üretip cihazı yeniden eşleştirin.

## Sık görülen sorunlar

| Belirti | Bakılacak yer |
|---|---|
| Logda `AUTH_INVALID_SIGNATURE (kod 1001)` | Sunucu saati: `timedatectl status` ("System clock synchronized: yes" olmalı). Sonra özel anahtarın doğru kopyalandığı. |
| Logda `AUTH_PERMISSION_DENIED (kod 1002)` | API anahtarının kapsamı (Trading → Full access), seçili hesap ve IP kısıtı. |
| Servis sürekli yeniden başlıyor | `sudo journalctl -u tradebot -n 80 --no-pager` çıktısındaki ilk hata satırı. |
| Dağıtım işi SSH'ta takılıyor | `VPS_KNOWN_HOSTS` ve `VPS_SSH_KEY` secret'ları; `deploy` kullanıcısının `authorized_keys` dosyası. |
