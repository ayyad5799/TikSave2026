# TikSave Pro — Deploy على Vercel

## هيكل المشروع
```
tiksave/
├── vercel.json          ← إعدادات Vercel
├── requirements.txt     ← Python packages
├── api/
│   ├── profile.py       ← جلب فيديوهات البروفايل
│   ├── download.py      ← رابط تحميل بدون علامة مائية
│   ├── upload.py        ← تحميل + رفع Dropbox
│   └── token.py         ← Dropbox OAuth token exchange
└── public/
    ├── index.html       ← الواجهة الكاملة
    └── auth-callback.html ← صفحة رجوع Dropbox OAuth
```

## خطوات النشر

### 1. ارفع على GitHub
```bash
git init
git add .
git commit -m "TikSave Pro"
git remote add origin https://github.com/YOUR_USERNAME/tiksave.git
git push -u origin main
```

### 2. انشر على Vercel
1. روح https://vercel.com وسجّل دخول
2. New Project ← Import من GitHub
3. اختر الـ repo
4. اضغط Deploy — خلاص! 🎉

### 3. إعداد Dropbox Redirect URI
بعد النشر، روح:
Dropbox App Console → Settings → Redirect URIs
أضف: `https://YOUR-PROJECT.vercel.app/auth-callback`

### 4. فتح الموقع
افتح `https://YOUR-PROJECT.vercel.app`
اضغط "الإعدادات" وأدخل المفاتيح.

## ملاحظة Vercel Free Plan
- Max function duration: 60 ثانية
- الفيديوهات الكبيرة ممكن تاخد وقت أطول
- Hobby plan مجاني ويكفي للاستخدام الشخصي
