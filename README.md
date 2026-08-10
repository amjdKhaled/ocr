# New Tracking for Laserfiche

يشغّل `NewTrackingAction.js` سجل اطلاع ديناميكيًا لقالب **تتبع**. يقرأ المستلمين من
حقل **المستلمون**، ويضيف المستخدم إلى قسم **تم الاطلاع** عند فتح الوثيقة.

## إعداد زر Web Access

```html
<li id="customNewTrackingButton" class="cmd-item lfActionItem">
  <a href="javascript:void(0);" class="lfActionBtn" role="menuitem" tabindex="0"
     title="تفعيل تتبع اطلاع المستلمين — النسخة الجديدة"
     onclick="window.runNewTrackingAction(); return false;">
    <span class="lfActionLabel">New Tracking</span>
  </a>
</li>
```

يجب تحميل `NewTrackingAction.js` قبل استعمال الزر. لا تستخدم الشرطات العكسية
المخصّصة لعرض Markdown داخل HTML الفعلي.

## صلاحيات Workflow المطلوبة

الحفظ التلقائي يتم من جلسة المستخدم الحالي عبر `SaveEntry`. لذلك فإن منح المستلم
`Browse (Brs)` و`Read (Rea)` فقط، مع وضع `Write Metadata (WMe)` ضمن **Denied**،
يمنع تسجيل الاطلاع ويؤدي إلى استجابة HTTP 401 أو 403.

اختر أحد الحلين التاليين:

1. امنح كل مستلم `WMe`، واحذف `WMe` من **Denied** في أنشطة Assign Rights 4–8.
2. إذا كان ممنوعًا منح المستخدمين تعديل البيانات الوصفية، انقل عملية التسجيل إلى
   Workflow/خدمة خلفية موثوقة تعمل بحساب `workflow`. لا ينبغي تضمين بيانات اعتماد
   حساب `workflow` في JavaScript المتصفح.

قفل الحقول الذي ينفذه السكربت في الواجهة وسيلة لتقليل التعديل العرضي فقط، وليس
بديلًا عن Laserfiche Field Security.

## تجنّب فقدان التسجيلات المتزامنة

يعيد السكربت قراءة السجل **بعد** قفل الوثيقة ثم يحفظه ويحرر القفل في جميع مسارات
النجاح والفشل. بهذه الطريقة لا تستبدل جلستان متزامنتان سجل إحداهما بالأخرى.
