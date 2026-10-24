# النشر على Vercel (مع Supabase)

## لماذا Supabase؟
Vercel لا يحتفظ بالملفات التي يكتبها التطبيق. لذلك الحسابات والتعليقات والترشيحات وصور CIN تُحفظ في Supabase
(قاعدة Postgres + تخزين خاص). الكود يختار Supabase تلقائياً إذا وُجد `SUPABASE_URL` و`SUPABASE_SERVICE_KEY`،
وإلا يستعمل ملفات محلية (للتطوير على حاسوبك).

## 1) Supabase
1. أنشئ مشروعاً على https://supabase.com
2. SQL Editor ← New query ← الصق محتوى `supabase_schema.sql` ← Run (ينشئ الجداول ويفعّل RLS وينشئ bucket خاص اسمه `kyc`).
3. Project Settings ← API Keys: انسخ **Project URL** و**Secret key** (`sb_secret_...`).
   (على مشروع قديم قد تجد `service_role` بدلها وهي تعمل أيضاً.)
4. Storage: تأكد أن bucket `kyc` **Private**.

## 2) GitHub
ارفع المجلد (بدون `.env`). الملف `.vercelignore` و`.gitignore` يستبعدان الملفات الحساسة.

## 3) Vercel
Add New ← Project ← اختر المستودع ← Framework: Flask. أضف Environment Variables:
`FLASK_SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `OMNIROUTE_API_KEY`, `OMNIROUTE_BASE_URL`, `OMNIROUTE_MODEL`,
`ADMIN_EMAILS`, `SMTP_*`, `TURNSTILE_*`, `GOOGLE_*` ثم Deploy.

## 4) بعد النشر
- Turnstile: أضف دومين Vercel في Hostnames.
- Google Sign-In: أضف `https://دومينك/login/google/callback` في Authorized redirect URIs.
- سجّل بإيميل `ADMIN_EMAILS` وأكّده لتظهر صفحة «Vérifications».

## حدود Vercel المعروفة
- حجم الطلب 4.5 ميغابايت: الصور تُضغط في المتصفح قبل الرفع، وملف CV الحد الأقصى 4 ميغابايت.
- كل ما يكتبه التطبيق يذهب إلى Supabase، لا إلى القرص.
