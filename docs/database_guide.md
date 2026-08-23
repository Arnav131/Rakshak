# 🗄️ Supabase + PostgreSQL Setup Guide — Rakshak Project

> **Yeh guide bilkul zero knowledge se start hoti hai.**
> Agar tumne kabhi Supabase nahi use kiya, koi baat nahi — har ek click explain hai.

---

## 📋 Tumhe Kya Kya Chahiye (Before You Start)

| Cheez | Kyun Chahiye |
|---|---|
| **Internet connection** | Supabase cloud pe hai, bina internet kuch nahi hoga |
| **GitHub account** | Supabase mein login karne ke liye (agar nahi hai toh neeche bana lenge) |
| **Yeh project folder** | `D:\PROTOTYPE_1.0` — yeh toh tumhare paas hai hi |
| **10-15 minute** | Itna time lagega poora setup karne mein |

---

## PART 1: GitHub Account (Agar Pehle Se Hai Toh Skip Karo)

> Agar tumhara GitHub account pehle se hai toh **seedha PART 2 pe jaao**.

### Step 1.1 — GitHub ki website kholo

1. Apna browser kholo (Chrome, Edge, Firefox — koi bhi chalega).
2. Address bar mein type karo: **`github.com`** aur Enter dabaao.
3. Ek green/dark page khulegi jisme likha hoga **"Let's build from here"** ya kuch similar.

### Step 1.2 — Sign Up karo

1. Page pe **"Sign up"** button dikhega — top right corner mein. Click karo.
2. Ek form aayega:
   - **Email address** — apna email daalo (Gmail, Outlook, kuch bhi chalega).
   - **Password** — ek strong password daalo (8+ characters, number + letter mix).
   - **Username** — ek unique naam choose karo (jaise `arnav-rakshak` ya kuch bhi).
3. **"Create account"** button pe click karo.
4. GitHub tumhare email pe ek **verification code** bhejega. Apna email inbox check karo, code copy karo, aur GitHub pe paste karo.
5. Done! GitHub account ban gaya. ✅

---

## PART 2: Supabase Account Banana

### Step 2.1 — Supabase ki website kholo

1. Browser mein **naya tab** kholo (Ctrl + T).
2. Address bar mein type karo: **`supabase.com`** aur Enter dabaao.
3. Supabase ki website khulegi — ek dark-themed page jisme likha hoga **"Build in a weekend. Scale to millions."** ya similar.

### Step 2.2 — Dashboard mein jaao

1. Page ke **bilkul top-right corner** mein ek green button hoga — **"Start your project"** ya **"Sign In"**.
   - Agar pehle kabhi Supabase use nahi kiya, toh dono buttons same jagah le jaayenge.
2. Click karo us button pe.

### Step 2.3 — GitHub se sign in karo

1. Ek naya page aayega jisme multiple sign-in options honge (GitHub, Google, etc.).
2. **"Continue with GitHub"** button pe click karo. Yeh sabse aasaan hai.
3. Agar tum GitHub mein already logged in ho toh:
   - Ek permission page aayega jisme likha hoga **"Authorize Supabase"**.
   - **"Authorize supabase"** green button pe click karo.
4. Agar GitHub mein logged in nahi ho toh:
   - Pehle GitHub ka login page aayega — apna GitHub email + password daalo.
   - Phir authorize page aayega — green button click karo.
5. Kuch seconds wait karo — tum **Supabase Dashboard** mein aa jaoge. ✅

> [!TIP]
> Dashboard ek dark-themed page hogi jisme left side pe ek sidebar hoga aur beech mein tumhare projects dikhenge (abhi koi project nahi hoga, toh khaali lagega).

---

## PART 3: Naya Supabase Project Banana

### Step 3.1 — "New Project" pe click karo

1. Dashboard pe tum ho. Ab do jagah se naya project bana sakte ho:
   - **Option A**: Page ke beech mein ek **"New Project"** button/card hoga — click karo.
   - **Option B**: Left sidebar mein top pe ek dropdown hoga organization ka naam ke saath. Uske paas ek **"+"** icon hoga — click karo aur **"New Project"** select karo.
2. Dono options same jagah le jaate hain.

### Step 3.2 — Project details bharo

Ek form khulega jisme 3 cheezein bharna hai:

#### 📝 Field 1: Project Name
- Yahan type karo: **`rakshak`**
- Yeh sirf display name hai, kuch bhi rakh sakte ho.

#### 🔒 Field 2: Database Password

> [!CAUTION]
> **YEH SABSE IMPORTANT STEP HAI. IS PASSWORD KO YAAD RAKHO YA KAHI LIKH LO!**
> Iske bina baad mein database se connect nahi kar paoge.

- **"Generate a password"** button pe click karo — Supabase khud ek strong password bana dega.
- **YA** apna password type karo (minimum 6 characters chahiye).
- ⚡ **ABHI KARO**: Password ko **Notepad mein paste karo ya phone pe screenshot lo**. Baad mein yeh password dikhega nahi.
  - Keyboard pe **Ctrl + C** se copy karo.
  - Notepad kholo (Windows key dabaao, `notepad` type karo, Enter).
  - **Ctrl + V** se paste karo.
  - File save karo kahi safe jagah pe.

#### 🌍 Field 3: Region
- Ek dropdown hoga region select karne ke liye.
- **"South Asia (Mumbai) - ap-south-1"** select karo.
  - Agar Mumbai option nahi dikh raha toh **"Southeast Asia (Singapore)"** select karo — yeh doosra closest hai.
- Region isliye important hai kyunki database physically us jagah pe hoga. Mumbai sabse fast hoga India ke liye.

### Step 3.3 — Project create karo

1. Saari fields bharne ke baad, neeche ek green button hoga — **"Create new project"**.
2. Click karo.
3. **Ab 2-3 minute wait karo.** ⏳
   - Screen pe likha aayega **"Setting up your project..."** ya ek loading animation dikhegi.
   - Supabase tumhare liye ek full PostgreSQL database bana raha hai cloud mein.
   - **Tab close mat karo. Refresh mat karo. Bas wait karo.**
4. Jab done ho jaayega toh tum apne project ke **Dashboard** pe aa jaoge.
   - Tumhe dikhega: **API keys, project URL**, aur ek welcome message.

> [!NOTE]
> Agar 5 minute se zyaada lag raha hai, toh page refresh karo (F5 ya Ctrl+R). Kabhi kabhi UI update nahi hoti but project ban chuka hota hai.

✅ Tumhara Supabase project ban gaya! Ab database bhi ban chuka hai — sirf connection string nikalna baaki hai.

---

## PART 4: DATABASE_URL Connection String Nikalna

> **Yeh wo magical link hai jo tumhare Django project ko Supabase database se connect karega.**

### Step 4.1 — Connect button dhundho

1. Tum abhi apne project ke Dashboard pe ho.
2. Page ke **top bar** mein (header area) ek **green "Connect"** button hoga.
   - Yeh usually top-right area mein hota hai, ya project name ke paas.
   - Kuch versions mein yeh naya "Connect" page hoti hai sidebar mein.
3. **"Connect"** button pe click karo.

### Step 4.2 — Connection type select karo

1. Ek modal (popup) ya naya page khulega jisme **3 options** dikhenge:
   
   | Option | Port | Kab Use Karo |
   |---|---|---|
   | **Direct Connection** | 5432 | Direct access, migrations ke liye |
   | **Transaction Pooler** | 6543 | Serverless functions ke liye |
   | **Session Pooler** | 5432 | ✅ **HUMEIN YEH CHAHIYE** — Django ke liye best |

2. **"Session Pooler"** tab/option pe click karo.
   - Agar tabs dikh rahe hain toh "Session Mode" ya "Session Pooler" wala click karo.

### Step 4.3 — URI copy karo

1. Session Pooler select karne ke baad, tumhe connection details dikhenge.
2. **"URI"** ya **"Connection String"** section dhundho.
3. Wahan ek lamba text hoga kuch aisa dikhega:

```
postgresql://postgres.abcdefghijk:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

4. **⚠️ DHYAN DO**: `[YOUR-PASSWORD]` ki jagah tumhara actual password hona chahiye.
   - Kuch dashboards mein password automatically filled hota hai.
   - Kuch mein `[YOUR-PASSWORD]` placeholder dikhata hai — isme tumhe **PART 3, Step 3.2** mein jo password save kiya tha woh manually dalna hoga.

5. **Poora URI copy karo**:
   - URI ke baaju mein ek **copy icon** (📋) hoga — click karo.
   - **YA** poora text select karo (click karke Ctrl+A) aur **Ctrl+C** dabaao.

### Step 4.4 — Verify karo ki URI sahi hai

Copy karne ke baad, Notepad mein paste karo (Ctrl+V) aur check karo:

```
postgresql://postgres.XXXXXXX:YYYYYY@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

✅ **Sahi hai agar**:
- `postgresql://` se start ho raha hai
- `postgres.` ke baad kuch random characters hain (tumhara project reference)
- `:` ke baad tumhara password hai (password mein `[YOUR-PASSWORD]` nahi likha hona chahiye — actual password hona chahiye)
- `@aws-` ke baad region hai
- `.pooler.supabase.com:5432/postgres` se end ho raha hai

❌ **Galat hai agar**:
- `[YOUR-PASSWORD]` literally likha hai — iska matlab password replace nahi hua. Toh manually replace karo us placeholder ko apne PART 3 wale password se.
- `sqlite` likha hai kahi — yeh galat URL hai.
- `:6543` port hai — tum Transaction Pooler use kar rahe ho, Session Pooler pe switch karo.

> [!IMPORTANT]
> Agar password mein koi **special character** hai jaise `@`, `#`, `%`, `!`, `/` toh woh URL mein problem de sakta hai.
> Agar aisa hai toh Supabase mein password reset karo bina special characters ke (sirf letters + numbers).
> Password reset karne ke liye: **Left sidebar → Project Settings (gear icon) → Database → Reset database password**.

---

## PART 5: `.env` File Mein DATABASE_URL Daalna

### Step 5.1 — `.env` file kholo

1. VS Code mein wapas aao (Alt+Tab se ya taskbar se).
2. **Left sidebar** mein file explorer hoga.
3. Project ke **root folder** (`PROTOTYPE_1.0`) mein ek file hai: **`.env`**
   - Agar `.env` dikh nahi rahi toh:
     - VS Code mein **Ctrl + Shift + P** dabaao.
     - Type karo: **"Open File"** aur Enter.
     - Path daalo: **`D:\PROTOTYPE_1.0\.env`**
     - Enter dabaao.
4. File khulegi, kuch aisa dikhega:

```
DEBUG=True
SECRET_KEY=rakshak-phase1-prototype-key-change-in-production
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=PLACEHOLDER_PASTE_YOUR_SUPABASE_URL_HERE
DATABASE_CONN_MAX_AGE=60
```

### Step 5.2 — URL paste karo

1. **Line 4** dhundho jahan `DATABASE_URL=PLACEHOLDER_PASTE_YOUR_SUPABASE_URL_HERE` likha hai.
2. `PLACEHOLDER_PASTE_YOUR_SUPABASE_URL_HERE` ko **select karo** (double-click karke ya click karke Shift+End).
3. **Ctrl + V** dabaao — tumhara Supabase URL paste ho jaayega.
4. Ab line kuch aisi dikhni chahiye:

```
DATABASE_URL=postgresql://postgres.abcdefghijk:tumhara_password@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

> [!WARNING]
> **`DATABASE_URL=` ke baad koi space nahi hona chahiye!**
> ❌ Galat: `DATABASE_URL= postgresql://...`
> ✅ Sahi: `DATABASE_URL=postgresql://...`
> Space hoga toh Django crash karega.

### Step 5.3 — File save karo

1. **Ctrl + S** dabaao.
2. Done! File saved. ✅

---

## PART 6: Check Karo Ki Connection Kaam Kar Raha Hai

### Step 6.1 — Terminal kholo

1. VS Code mein **Ctrl + `** dabaao (backtick key — Esc ke neeche hota hai).
   - Ya upar menu mein: **Terminal → New Terminal**.
2. Terminal panel neeche khulega.

### Step 6.2 — Virtual environment activate karo

Terminal mein yeh type karo aur Enter dabaao:

```powershell
D:\PROTOTYPE_1.0\venv\Scripts\Activate.ps1
```

> Agar PowerShell error de toh yeh try karo:
> ```powershell
> D:\PROTOTYPE_1.0\venv\Scripts\activate.bat
> ```

Activate hone ke baad terminal line ke start mein **(venv)** likha dikhega. Yeh sign hai ki virtual environment on hai.

### Step 6.3 — Test command chalaao

```powershell
cd D:\PROTOTYPE_1.0\backend
python manage.py check
```

### Step 6.4 — Result dekho

**✅ Agar sahi hai toh output aayega:**
```
System check identified no issues (0 silenced).
```
Yeh matlab connection successful hai! 🎉

**❌ Agar error aaya toh:**

| Error Message | Matlab | Fix |
|---|---|---|
| `ImproperlyConfigured: DATABASE_URL is required` | `.env` mein `DATABASE_URL` nahi mila | `.env` file mein check karo — kya paste kiya hai? |
| `could not connect to server: Connection refused` | Supabase se connection fail hua | Internet check karo. URL mein password sahi hai? |
| `password authentication failed` | Password galat hai | PART 4, Step 4.4 mein wala check karo — password `[YOUR-PASSWORD]` toh nahi likha? |
| `could not translate host name` | URL mein host galat hai | URL dobara copy karo Supabase se — kuch cut ho gaya hoga |
| `SSL connection is required` | SSL missing | URL ke end mein `?sslmode=require` add karo |
| `ModuleNotFoundError: No module named 'django'` | Virtual env active nahi hai | Step 6.2 dobara karo — venv activate karo |

---

## PART 7: Connection Successful Hone Ke Baad Kya Karna Hai

> [!IMPORTANT]
> **Jab `python manage.py check` successfully chal jaaye (0 errors), toh bas mujhe bata do:**
>
> *"Supabase connected hai, `manage.py check` mein 0 errors aaye"*
>
> Baaki sab kuch (migrate, seed data, server start) **main kar dunga**! 🚀

---

## 🆘 Emergency Fixes

### Password bhool gaye?
1. Supabase Dashboard pe jaao → apna project kholo.
2. **Left sidebar** mein neeche ek **gear icon** (⚙️) hoga — **"Project Settings"** pe click karo.
3. Left mein **"Database"** tab pe click karo.
4. **"Database Password"** section mein ek **"Reset database password"** button hoga.
5. Naya password daalo (simple rakho — sirf letters aur numbers, no special characters).
6. **"Update password"** pe click karo.
7. Ab wapas jaao **PART 4** pe aur naya connection string copy karo naye password ke saath.

### Supabase dashboard nahi khul raha?
- **`app.supabase.com`** try karo directly.
- VPN on hai toh off karo.
- Incognito/Private window mein try karo (Ctrl + Shift + N).

### `python` command nahi chal raha?
- Iska matlab Python install nahi hai ya PATH mein nahi hai.
- Terminal mein try karo: **`py manage.py check`** (sirf `py` use karo `python` ki jagah).
- Agar woh bhi na chale: **`python3 manage.py check`** try karo.

### Virtual environment activate nahi hai?
Agar error aaye ki `django` module not found, toh pehle venv activate karo:
```powershell
D:\PROTOTYPE_1.0\venv\Scripts\Activate.ps1
```
Agar PowerShell error de toh:
```powershell
D:\PROTOTYPE_1.0\venv\Scripts\activate.bat
```
Phir dobara `python manage.py check` chalaao.

---

> **Yaad rakho**: Supabase ka free tier **2 projects** allow karta hai. Ek project pe **500 MB** database storage milta hai. Hamare Rakshak prototype ke liye yeh kaafi hai.
>
> Koi bhi step mein atke toh mujhe bata do — main help kar dunga! 💪
