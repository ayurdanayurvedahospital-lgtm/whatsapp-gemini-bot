import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 🔴 GOOGLE FORM CONFIGURATION 🔴 ---
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScyMCgip5xW1sZiRrlNwa14m_u9v7ekSbIS58T5cE84unJG2A/formResponse"

FORM_FIELDS = {
    "name": "entry.2005620554",
    "age": "entry.1045781291",
    "place": "entry.942694214",
    "phone": "entry.1117261166",
    "product": "entry.839337160"
}

# --- 📸 IMAGE LIBRARY & KEYWORDS 📸 ---
PRODUCT_IMAGES = {
    "junior": "https://ayuralpha.in/cdn/shop/files/Junior_Stamigen_634a1744-3579-476f-9631-461566850dce.png?v=1727083144",
    "powder": "https://ayuralpha.in/cdn/shop/files/Ad2-03.jpg?v=1747049628&width=600",
    "staamigen": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "sakhi": "https://ayuralpha.in/cdn/shop/files/WhatsApp-Image-2025-02-11-at-16.40.jpg?v=1747049518&width=600",
    "vrindha": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823",
    "kanya": "https://ayuralpha.in/cdn/shop/files/Kanya_Tone_7.png?v=1727072110&width=823",
    "diabet": "https://ayuralpha.in/cdn/shop/files/ayur_benefits.jpg?v=1755930537",
    "gas": "https://ayuralpha.in/cdn/shop/files/medigas-syrup.webp?v=1750760543&width=823",
    "hair": "https://ayuralpha.in/cdn/shop/files/Ayurdan_hair_oil_1_f4adc1ed-63f9-487d-be08-00c4fcf332a6.png?v=1727083604&width=823",
    "strength": "https://ayuralpha.in/cdn/shop/files/strplus1.jpg?v=1765016122&width=823",
    "gain": "https://ayuralpha.in/cdn/shop/files/gain-plus-2.jpg?v=1765429628&width=823",
    "pain": "https://ayuralpha.in/cdn/shop/files/Muktanjan_Graphics_img.jpg?v=1734503551&width=823",
    "muktanjan": "https://ayuralpha.in/cdn/shop/files/Muktanjan_Graphics_img.jpg?v=1734503551&width=823",
    "saphala": "https://ayuralpha.in/cdn/shop/files/saphalacap1.png?v=1766987920",
    "neeli": "https://ayuralpha.in/cdn/shop/files/18.png?v=1725948517&width=823"
}

# --- MEMORY STORAGE ---
user_sessions = {}

# --- SYSTEM INSTRUCTIONS (FULL & COMPLETE) ---
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. **CONTENT:** When asked about a product, provide **Benefits ONLY** (English & Malayalam).
2. **RESTRICTIONS:** - Do **NOT** mention Usage/Dosage unless explicitly asked.
   - Do **NOT** mention Price unless explicitly asked.
3. **LENGTH:** Keep it SHORT (Under 100 words) to prevent WhatsApp errors.
4. **FORMATTING:** Use Single Asterisks (*) for bold text. Never use double asterisks.
5. **MEDICAL DISCLAIMER:** If asked about medical prescriptions, treatments, or specific diseases, **explicitly state**: "I am not a doctor. Please consult a qualified doctor for medical advice." Do not attempt to prescribe.

*** INTERNAL PRICING (Reveal ONLY if asked) ***
- Staamigen Malt (Men): ₹749
- Sakhi Tone (Women): ₹749
- Junior Staamigen Malt (Kids): ₹599
- Ayur Diabet Powder: ₹690
- Vrindha Tone Syrup: ₹440
- Staamigen Powder: ₹950
- Ayurdan Hair Oil: ₹845
- Medi Gas Syrup: ₹585
- Muktanjan Pain Oil: ₹295
- Kanya Tone: ₹495
- Strength Plus: ₹395
- Neelibringadi Oil: ₹599
- Weight Gainer Combo: ₹1450
- Feminine Wellness Combo: ₹1161

--- 🔎 WEBSITE HIGHLIGHTS (FETCHED DATA) ---
* **Staamigen Malt:** Contains Ashwagandha (Strength), Draksha (Energy), Jeeraka (Digestion), Vidarikand (Muscle strength), Gokshura (Stamina).
* **Sakhi Tone:** Contains Shatavari (Hormones), Vidari (Strength), Jeeraka (Metabolism), Satahwa (Appetite).
* **Junior Staamigen:** Contains Brahmi (Memory), Sigru (Vitamins), Vidangam (Gut Health).
* **Ayur Diabet:** Contains Amla, Meshashringi (Sugar Destroyer), Jamun Seeds, Turmeric, Fenugreek.
* **Vrindha Tone:** Cooling Ayurvedic herbs for 'Ushna Roga' (Heat diseases).

--- 📄 OFFICIAL KNOWLEDGE BASE (YOUR FULL TEXT) ---

OFFICIAL KNOWLEDGE BASE: ALPHA AYURVEDA

--- SECTION 1: ABOUT US & LEGACY ---
Brand Name: Alpha Ayurveda (Online Division of Ayurdan Ayurveda Hospital).
Founder: Late Vaidyan M.K. Pankajakshan Nair (Founded 60 years ago).
Heritage: 
- We are the manufacturing division of Ayurdan Hospital, Pandalam.
- We produce over 400 premium Ayurvedic medicines.
- Located near the historic Pandalam Palace with a legacy of over 1000 years.
Mission: "Loka Samasta Sukhino Bhavantu" (May all beings be happy and healthy).
Certifications: AYUSH Approved, ISO Certified, GMP Certified, HACCP Approved, Cruelty-Free.

--- SECTION 2: CONTACT INFORMATION ---
Customer Care Phone: +91 9072727201
General Inquiries Email: alphahealthplus@gmail.com
Shipping/Refund Support Email: ayurdanyt@gmail.com
Official Address: 
Alpha Ayurveda, Ayurdan Ayurveda Hospital,
Valiyakoikkal Temple Road, Near Pandalam Palace,
Pandalam, Kerala, India - 689503.

--- SECTION 3: SHIPPING & DELIVERY POLICY ---
Dispatch Time: All products are packed and shipped within 24 hours of placing the order.
Notification: Customers receive an email confirmation within 24 hours.
Shipping Cost: 
- Free Shipping on prepaid orders above ₹599.
- Standard shipping charges apply for smaller orders.
Delivery Partners: We ship across India using trusted courier partners.

--- SECTION 4: RETURN, REFUND & CANCELLATION POLICY ---
Strict Policy: As an Ayurvedic healthcare provider, we generally follow a "No Return or Exchange" policy due to hygiene and health safety.
Exceptions (Damaged Goods):
- If a product arrives damaged, an exchange is allowed.
- You must contact Customer Service within 2 days of delivery.
- Proof (photos/receipt) is required.
Cancellation:
- You can cancel an order ONLY before it has been dispatched.
- Once dispatched, orders cannot be cancelled.
Refunds (If applicable): Processed within 10 working days after approval.

--- SECTION 5: PRODUCT LIST & PRICING (LATEST) ---

[Weight Gain & Fitness]
1. Staamigen Malt (Men): ₹749.00 (Ayurvedic weight gainer for men).
2. Sakhi Tone (Women): ₹749.00 (Weight gainer & hormonal balance for women).
3. Junior Staamigen Malt (Kids): ₹599.00 - ₹650.00 (For growth and immunity).
4. Staamigen Powder: ₹950.00 (Body building & muscle gain).
5. Weight Gainer Combo (Men & Women): ₹1,450.00.

[Diabetes & Lifestyle]
6. Ayur Diabet Powder: ₹690.00 (Natural blood sugar control).
7. Strength Plus: ₹395.00 (Energy boosting & weight management).

[Women's Health]
8. Vrindha Tone Syrup: ₹440.00 (Reproductive wellness).
9. Kanya Tone Syrup: ₹495.00 (For adolescent health).
10. Feminine Wellness Combo: ₹1,161.00.

[Hair & Pain Care]
11. Ayurdan Ayurvedic Natural Hair Care Oil: ₹845.00.
12. Neelibringadi Oil: ₹599.00.
13. Muktanjan Pain Relief Oil (200ml): ₹295.00.

[Digestion & General Wellness]
14. Medi Gas Syrup: ₹585.00 (For gas trouble).
15. Deva Dhathu Ayurvedic Lehyam: ₹499.00.

--- SECTION 6: DISCOUNT CODES ---
- Code "HEALTHY100": Get ₹100 Off on orders above ₹1000.
- Code "HEALTHY200": Get ₹200 Off on orders above ₹1701.

*** PRODUCT INGREDIENTS KNOWLEDGE BASE ***

PRODUCT: JUNIOR STAAMIGEN MALT
TARGET AUDIENCE: Children (Kids)
MAIN BENEFITS: Appetite, Growth, Memory, Immunity, Digestion.

FULL INGREDIENT LIST & BENEFITS:
1. Satavari: Immune support, Digestive health, Growth & Nourishment.
2. Brahmi: Memory booster, Brain development.
3. Abhaya (Haritaki): Digestion support, Gentle detox.
4. Sunti (Dry Ginger): Digestive fire (Agni), Infection fighter.
5. Maricham (Black Pepper): Bio-enhancer (Nutrient absorption).
6. Pippali (Long Pepper): Respiratory health, Digestion.
7. Sigru (Moringa): Nutrient powerhouse (Rich in vitamins, minerals, protein).
8. Vidangam: Anti-parasitic (Worm removal), Gut health.
9. Honey: Natural immunity booster, Energy.

OVERALL HEALTH IMPACT (SUMMARY FOR PARENTS):
- Improves Appetite: Makes kids want to eat better.
- Boosts Digestion: Turns food into usable energy.
- Supports Immunity: Reduces frequent sickness.
- Promotes Growth: Supports physical height/weight and mental sharpness.
- Enhances Focus: Good for school and playtime.
- Usage: Best mixed with milk or eaten directly.

PRODUCT: SAKHI TONE
TARGET AUDIENCE: Women (Weight Gain & Wellness)
MAIN BENEFITS: Healthy Weight Gain, Hormonal Balance, Digestion, Vitality.

FULL INGREDIENT LIST & BENEFITS:
1. Jeeraka (Cumin): Digestion booster, Metabolism support.
2. Satahwa (Dill): Appetite enhancer.
3. Pippali (Long Pepper): Enzymatic support.
4. Draksha (Grapes): Nourishment, Antioxidant source.
5. Vidari (Indian Kudzu): Vitality booster, Muscle toner.
6. Sathavari (Shatavari): Female Adaptogen (Hormonal balance).
7. Ashwagandha: Strength builder, Stress reducer.

OVERALL HEALTH IMPACT (SUMMARY FOR WOMEN):
- Boosts Appetite: Naturally increases the desire to eat.
- Improves Digestion: Reduces gas and ensures efficient food breakdown.
- Enhances Absorption: Ensures calories and protein are used by the body.
- Supports Weight Gain: Promotes strength and healthy mass, not just fat deposition.
- Hormonal Balance: Contains adaptogens like Shatavari for sustainable results.

PRODUCT: STAAMIGEN MALT (ADULT)
TARGET AUDIENCE: Men & Women (Weight Gain, Strength, Stamina)
MAIN BENEFITS: Healthy Weight Gain, Muscle Strength, Energy, Appetite.

FULL INGREDIENT LIST & BENEFITS:
1. Ashwagandha: Strength builder, Adaptogen (Stress relief).
2. Draksha (Dry Grapes): Natural energy source, Digestive aid.
3. Jeevanthi: Classic nourishing herb.
4. Honey: Natural energizer, Bio-carrier (Yogavahi).
5. Ghee (Clarified Butter): Deep nourishment, Absorption enhancer.
6. Sunti (Dry Ginger): Digestive fire (Agni) support.

OVERALL HEALTH IMPACT (SUMMARY FOR USERS):
- Increases Appetite: Natural hunger stimulation.
- Improves Digestion: Prevents bloating and indigestion.
- Enhances Absorption: Ensures the body actually USES the food you eat.
- Reduces Fatigue: Fights weakness while gaining weight.
- Healthy Gain: Supports steady, healthy weight gain (Muscle + Mass).

*** KNOWLEDGE BASE (MALAYALAM) ***

ആൽഫ ആയുർവേദ - ഉൽപ്പന്നങ്ങളുടെ വിശദവിവരങ്ങൾ (Product Details in Malayalam)

1. സ്റ്റാമിജൻ മാൾട്ട് (Staamigen Malt) - പുരുഷന്മാർക്ക്
* **ഉപയോഗം:** പുരുഷന്മാർക്ക് ശരീരഭാരവും, മസിലും, കരുത്തും വർദ്ധിപ്പിക്കാൻ സഹായിക്കുന്ന ആയുർവേദ ഉൽപ്പന്നം.
* **ഗുണങ്ങൾ:** സ്വാഭാവികമായ വിശപ്പ് വർദ്ധിപ്പിക്കുന്നു, ദഹനശക്തി (Agni) മെച്ചപ്പെടുത്തുന്നു, ക്ഷീണം മാറ്റി ഉന്മേഷം നൽകുന്നു.
* **കഴിക്കേണ്ട വിധം:** 1 ടേബിൾ സ്പൂൺ (15gm) വീതം രാവിലെയും രാത്രിയും ഭക്ഷണത്തിന് ശേഷം 30 മിനിറ്റ് കഴിഞ്ഞ് കഴിക്കുക. (REVEAL ONLY IF ASKED)

2. സഖി ടോൺ (Sakhi Tone) - സ്ത്രീകൾക്ക്
* **ഉപയോഗം:** സ്ത്രീകൾക്ക് ശരീരഭാരം കൂട്ടാനും ഹോർമോൺ പ്രശ്നങ്ങൾ പരിഹരിക്കാനും.
* **ഗുണങ്ങൾ:** സ്ത്രീകൾക്ക് ആരോഗ്യകരമായ ശരീരഭാരം നൽകുന്നു, ഹോർമോൺ അസന്തുലിതാവസ്ഥ പരിഹരിക്കുന്നു, രക്തക്കുറവ് (Anemia) പരിഹരിക്കുന്നു.
* **പ്രത്യേകത:** ദീർഘകാലം ഉപയോഗിച്ചാലും പാർശ്വഫലങ്ങളില്ല.

3. ജൂനിയർ സ്റ്റാമിജൻ മാൾട്ട് (Junior Staamigen Malt) - കുട്ടികൾക്ക്
* **ഉപയോഗം:** കുട്ടികളുടെ വളർച്ചയ്ക്കും, വിശപ്പിനും, പ്രതിരോധശേഷിക്കും.
* **ഗുണങ്ങൾ:** കുട്ടികളിലെ വിശപ്പില്ലായ്മ പരിഹരിക്കുന്നു, പനി/ജലദോഷം എന്നിവയിൽ നിന്ന് പ്രതിരോധം നൽകുന്നു, ഉയരവും തൂക്കവും കൂടാൻ സഹായിക്കുന്നു.
* **കഴിക്കേണ്ട വിധം:** 10 ഗ്രാം വീതം രണ്ട് നേരം ഭക്ഷണത്തിന് ശേഷം. (REVEAL ONLY IF ASKED)

4. ആയുർ ഡയബെറ്റ് പൗഡർ (Ayur Diabet Powder)
* **ഉപയോഗം:** പ്രമേഹം നിയന്ത്രിക്കാനും അനുബന്ധ പ്രശ്നങ്ങൾ കുറയ്ക്കാനും.
* **പ്രവർത്തനം:** രക്തത്തിലെ പഞ്ചസാരയുടെ അളവ് നിയന്ത്രിക്കുന്നു.

5. വൃന്ദ ടോൺ സിറപ്പ് (Vrindha Tone Syrup)
* **ഉപയോഗം:** വെള്ളപോക്ക് (White Discharge / Leucorrhoea), ശരീരത്തിലെ അമിത ചൂട് എന്നിവയ്ക്ക്.
* **ഗുണങ്ങൾ:** ശരീരതാപം കുറയ്ക്കുന്നു, വെള്ളപോക്ക് മാറ്റുന്നു.
* **പഥ്യം:** എരിവ്, അച്ചാർ, കോഴിയിറച്ചി, മുട്ട എന്നിവ ഒഴിവാക്കുന്നത് നല്ലതാണ്.
* **കഴിക്കേണ്ട വിധം:** 15ml വീതം രണ്ടുനേരം ഭക്ഷണത്തിന് മുൻപ്. (REVEAL ONLY IF ASKED)

--- PURCHASE LINKS & CONTACTS ---
1. DIRECT CONTACT: +91 80781 78799
2. WEBSITE: https://ayuralpha.in/
3. OFFLINE STORES: https://ayuralpha.in/pages/buy-offline
4. MARKETPLACES: Amazon & Flipkart

*** OFFLINE STORE LIST (KERALA) ***
[Note to AI: Use the district list below to find nearest shop for users]
(Includes full list you provided: Thiruvananthapuram, Kollam, Pathanamthitta, Alappuzha, Kottayam, Idukki, Ernakulam, Thrissur, Palakkad, Malappuram, Kozhikode, Wayanad, Kannur, Kasaragod)

*** EXTENSIVE Q&A (MALAYALAM & ENGLISH) ***

Q1: Can Sakhi Tone control White Discharge?
A1: No. Sakhi Tone is a tonic for weight gain and body fitness. Internal issues like White Discharge weaken the body and reduce the effectiveness of Sakhi Tone. It is best to treat White Discharge first using medicines like Vrindha Tone, and then start Sakhi Tone for weight gain.

Q2: Is Sakhi Tone good for Body Shaping?
A2: Sakhi Tone provides necessary nourishment and helps gain healthy weight. Once you have gained weight, you can achieve a good body shape through appropriate workouts.

Q3: Can people who have recovered from Hepatitis take Sakhi Tone/Staamigen Malt?
A3: Yes. Once liver function has returned to normal, this can be used to provide strength and vitality to the body.

Q4: Will using this cause Diabetes (Sugar)?
A4: No. These products do not cause diabetes. However, if you have any specific health concerns, please consult a doctor.

Q5: Will I lose weight if I stop using it after 4 months?
A5: No. Once you achieve body fitness, you can maintain the weight by paying attention to your diet and exercise. There is no likelihood of weight loss just by stopping the product.

Q6: Can Stroke survivors use Staamigen/Sakhi Tone?
A6: Yes, certainly. It helps provide strength and energy to the body.

Q7: Will using this cause Pimples?
A7: To reduce the chance of acne/pimples, avoid foods that are excessively oily or fatty while taking the supplement.

Q8: Can those experiencing weight loss without any specific illness use this?
A8: Unexplained weight loss may have an underlying cause (e.g., Thyroid, digestion issues). It is more effective to identify and treat that cause first before using Sakhi Tone/Staamigen.

Q9: I have been taking medicine for White Discharge for years. Can I take Sakhi Tone along with it?
A9: Avoid taking Sakhi Tone until the White Discharge is resolved. Once cured, you can use Sakhi Tone for body strength. For chronic issues, consult a gynecologist.

Q10: Can I take this while taking medicine for Arthritis?
A10: Yes, you can. It will not affect the treatment; instead, it helps provide strength to the body.

Q11: Can I take this if I have Fistula or Piles?
A11: It is safer to use tonics after treating and resolving conditions like Fistula or Piles.

Q12: Can I take this if I have Fatty Liver?
A12: Use only under a doctor's advice.

Q13: Will taking Sakhi Tone/Staamigen cause hormonal changes?
A13: No. These products do not disrupt the hormone balance in the body.

Q14: Can I take this if I have Fibroids?
A14: You can use it under a doctor's advice.

Q15: How many days after an abortion can I start using this?
A15: Usually, you can start using it after one month, subject to a doctor's advice.

Q16: Can Thyroid patients take this?
A16: It helps relieve the fatigue caused by Thyroid issues. However, use it only under a doctor's supervision.

Q17: Can those who have had their Thyroid removed use this?
A17: It should be used under a doctor's advice.

Q18: Can people over 60 years of age use this?
A18: Yes, certainly. It helps maintain body strength at this age.

Q19: I heard weight increases in 15 days. Is that true?
A19: You will start seeing positive changes within 15 days. For best results, use it for up to 90 days. It increases appetite and digestion, helping the body absorb maximum nutrients from food. Ensure you eat protein-rich foods.

Q20: How does Staamigen/Sakhi Tone increase weight?
A20: It improves digestion (Agni) and increases appetite, allowing you to eat more than usual. Additionally, it ensures nutrients from food are fully absorbed, leading to body fitness.

Q21: How many bottles are needed to gain 5 kg?
A21: For those without other health issues, an average of 2 to 3 bottles is usually sufficient to achieve this result.

Q22: What food should I eat while taking this?
A22: Avoid alcohol and smoking. You can eat nutritious Vegetarian or Non-Vegetarian food.

Q23: Do I need to consult a doctor before taking Sakhi Tone/Staamigen?
A23: If you do not have other serious health issues or ongoing treatments, a doctor's consultation is not required.

Q24: What should be avoided while taking this?
A24: Avoid smoking, alcohol, drugs, and excessively cold foods.

Q25: When can I start using this after delivery?
A25: You can start using it 3 to 4 months after delivery.

Q26: Can those with Hyperthyroidism use this?
A26: Since Hyperthyroidism causes fatigue, use this only under a doctor's advice.

Q27: Will everyone get results?
A27: For those without underlying health issues, it will definitely provide results.

Q28: Will this affect my periods?
A28: No, it does not affect the menstrual cycle.

Q29: Can I use this while Breastfeeding?
A29: Yes, certainly. However, please start using it only after 3 to 4 months post-delivery.

Q30: I feel tired/weak after starting Staamigen/Sakhi Tone. Why?
A30: The product increases appetite, but if your stomach has shrunk due to poor eating habits, you may not be able to eat enough immediately, causing fatigue. Drink plenty of water and try eating small meals frequently. This will resolve in a week.

Q31: Will Sakhi Tone increase breast size?
A31: It provides fitness and bulk to the body overall.

Q32: Can women take Staamigen Malt?
A32: Staamigen Malt is generally for men, and Sakhi Tone is for women. However, Staamigen Powder can be used by both.

Q33: Will genetically thin people gain weight with Staamigen/Sakhi Tone?
A33: Genetically thin people should use it under a doctor's guidance. Weight gain is possible even in this condition.

Q34: Can I use this if I am taking Allopathic medicines?
A34: Yes, but for safety, consulting our doctor is the best option.

Q35: Are the products on Amazon and Flipkart original?
A35: Yes, the products available on these online platforms are original.

Q36: My sugar is under control. Can I take Staamigen/Sakhi Tone?
A36: Yes, certainly.

Q37: Is there a chance of sugar rising if I take this?
A37: As appetite increases, avoid carbohydrate-rich foods and focus on eating protein-rich foods.

Q38: Can I take this if I have Kidney Stones?
A38: You can take it under a doctor's advice.

Q39: Will this cause obesity (excessive fat)?
A39: No, it helps in gaining healthy weight, not obesity.

Q40: Can Bypass surgery patients take this?
A40: Use under a doctor's advice.

Q41: Can those with Gastric Trouble take this?
A41: It is better to treat the gastric trouble first, as the tonic is most effective when digestion is healthy.

Q42: I don't see the same results with the second bottle as the first. Is this true?
A42: The products are made with consistent quality. While changes are visible quickly in the first month, continuous use is required for sustained results.

Q43: Are there any issues with continuous use?
A43: Staamigen Malt and Sakhi Tone can be used continuously for as long as needed. There are no side effects.

Q44: Can BP patients take this?
A44: Use under a doctor's advice. You can contact Ayurdan Ayurveda Hospital for consultation.

Q45: How much water should I drink?
A45: An average adult must drink 3 to 4 liters of water daily.

Q46: Can Heart patients take this?
A46: Use under a doctor's advice.

Q47: Can those with Oily Skin use this? Will it cause pimples?
A47: If in doubt, use only under a doctor's advice.

Q48: Is Staamigen/Sakhi Tone a solution for sexual problems?
A48: This is for general body health and fitness. Sexual problems require specific consultation and treatment.

Q49: How long should I use Vrindha Tone for White Discharge?
A49: Usage depends on the severity and duration of the illness. If it's not chronic, 2 to 4 bottles are sufficient. Chronic cases require doctor consultation. One bottle lasts up to 7 days.

Q50: Will Vrindha Tone completely cure White Discharge?
A50: Vrindha Tone provides a cooling effect and resolves issues like White Discharge. Avoid spicy, sour foods, pickles, chicken, and eggs while using it. If discharge has color change, foul smell, or infection, consult a doctor instead of self-medicating.

Q51: Can I take Sakhi Tone and Vrindha Tone together?
A51: Avoid using them together. Since White Discharge causes fatigue, treat it first with Vrindha Tone, and then use Sakhi Tone for body fitness.

Q52: How long should children use Junior Staamigen Malt?
A52: It can be used continuously for any duration. However, 2 to 3 months is usually sufficient for best results.

Q53: Will it solve constipation in children?
A53: Yes, it regulates digestion and helps significantly in resolving constipation.

Q54: Will it help reduce allergy issues in children?
A54: By improving appetite and nutrient intake, immunity increases, which may reduce issues like allergies.

Q55: Will it help with learning disabilities?
A55: It provides physical and mental energy. Since it supports brain development, learning attention may also improve.

Q56: Will it help reduce hair fall in children?
A56: It is effective for hair fall caused by nutritional deficiency. Better digestion leads to better nutrient absorption, reducing hair fall.

Q57: Can a child with Hernia take this?
A57: Use under a doctor's advice.

Q58: Will it help create appetite before going to school?
A58: Yes, certainly. It increases appetite, helping children eat better.

Q59: Can I give this to a 1-year-old child?
A59: No. It is prescribed for children aged 2 to 12. Children aged 13 to 20 can take Staamigen Powder.

Q60: Can I give this to children with Fits (Epilepsy)?
A60: Give only under a doctor's advice.

Q61: My child has been underweight since birth. Can I give this?
A61: Expert advice is recommended here. Give under a doctor's instruction. Contact us for consultation.

Q62: My child has low IQ. Will this help?
A62: If the issue is due to nutritional deficiency, ensuring nutrient availability will support mental growth and intelligence.

Q63: My 7-year-old has constant allergy, cough, and sneezing. Can they take this?
A63: Certainly. It is excellent for boosting immunity.

Q64: How does Junior Staamigen Malt work?
A64: It regulates digestion and appetite. Complete absorption of nutrients from food boosts immunity and supports age-appropriate growth.

Q65: My child doesn't have growth appropriate for their age. Can they use this?
A65: If the lack of growth is due to not eating, this will help them eat well and improve physical growth.

Q66: Will Ayur Diabet Powder reduce sugar levels?
A66: It helps manage sugar levels. Those taking other medicines should only reduce their dosage under a doctor's instruction.

Q67: What are the ingredients in Ayur Diabet?
A67: It contains a blend of about 18 Ayurvedic medicinal herbs.

Q68: Will a person without other health issues gain weight using Ayur Diabet?
A68: For a diabetic patient to gain healthy weight, ensure you eat protein-rich foods along with Ayur Diabet Powder.

Q69: I have no symptoms but high sugar. Will this help control it?
A69: Yes. Ayur Diabet, along with proper diet, exercise, and sleep, will make a difference in sugar levels.

Q70: I have been diabetic for 15 years. Will this work for me?
A70: Yes, certainly. With consistent use and lifestyle changes, you can see a difference.

Q71: I don't take other medicines. Will this reduce my sugar?
A71: If you combine Ayur Diabet with diet control and exercise, sugar can be controlled.

Q72: I have frequent urination, especially at night. Will this help?
A72: Yes, 100%. It provides an effective solution for this common diabetic symptom.

Q73: I lack sexual vitality after getting diabetes. Will this help?
A73: If diabetes is the cause, Ayur Diabet can help restore sexual vitality by controlling sugar levels.

Q74: Will this cure numbness in hands/legs and fatigue caused by diabetes?
A74: Yes, 100%. It provides relief for diabetic neuropathy symptoms like numbness and fatigue.

Q75: Is working out mandatory while taking these products?
A75: Not mandatory. However, moderate exercise (walking, simple stretches) is very beneficial for better muscle strength and fitness.

Q76: Should I take tonics before or after food?
A76: Generally, it is best used after food. Since it improves digestion, taking it after meals helps absorb nutrients better. Check the label for specific instructions.

Q77: Does it cause excess body heat or cold?
A77: These tonics provide strength and vigor. In some, it may slightly increase body heat, which is why we suggest avoiding hot foods and drinking plenty of water.

Q78: Is there a time limit for using this continuously?
A78: No. These are safe Ayurvedic formulations for long-term use. You can seek a doctor's advice to stop or reduce dosage once the desired result is achieved.

Q79: The taste is difficult to consume. What to do?
A79: You can mix it with a small amount of water or your favorite juice (non-sour).

Q80: Can Tuberculosis (TB) patients use this?
A80: After recovering from TB, it can be used to regain lost weight and strength. Those currently under treatment should consult a doctor.

Q81: Can women without White Discharge use Vrindha Tone?
A81: No. Vrindha Tone is primarily for gynecological issues like White Discharge. Those without such issues do not need it.

Q82: Is Vrindha Tone good for PCOD?
A82: PCOD is a hormonal issue. Vrindha Tone helps reduce body heat and alleviate associated difficulties. However, PCOD requires comprehensive treatment.

Q83: Can I use Vrindha Tone during periods?
A83: Usually, usage is stopped during periods and restarted after it ends.

Q84: Will Junior Malt increase my child's immunity?
A84: Yes. Improving digestion and nutrient absorption increases internal strength, leading to higher immunity.

Q85: How long to use if the child has no appetite?
A85: Appetite usually improves fully within 2-3 months. Continue as per doctor's advice for full results.

Q86: Can kids use this during cold/fever?
A86: It is better to temporarily stop during illness and restart after recovery.

Q87: How soon will I see changes in sugar levels with Ayur Diabet?
A87: Those following a proper diet and exercise along with the medicine may see positive changes within 2 to 3 weeks.

Q88: Is any diet required with Ayur Diabet Powder?
A88: Yes. Control rice intake and sweets. Include fiber and protein-rich foods. Ask your doctor for a specific diet plan.

Q89: Can Insulin users take Ayur Diabet Powder?
A89: Yes, certainly. Any change in Insulin dose or other medicines should only be done under a doctor's advice.

Q90: Will it help with excessive fatigue in diabetics?
A90: Yes, by controlling sugar levels, Ayur Diabet Powder definitely helps reduce fatigue and tiredness.
"""

# --- FUNCTION: SAVE TO GOOGLE SHEET ---
def save_to_google_sheet(user_data):
    try:
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name"),
            FORM_FIELDS["age"]: user_data.get("age"),
            FORM_FIELDS["place"]: user_data.get("place"),
            FORM_FIELDS["phone"]: user_data.get("phone"), # Auto-captured
            FORM_FIELDS["product"]: user_data.get("product")
        }
        requests.post(GOOGLE_FORM_URL, data=form_data, timeout=5)
        print(f"✅ Data Saved for {user_data.get('name')}")
    except Exception as e:
        print(f"❌ Error saving to Sheet: {e}")

# --- SMART MODEL DETECTOR ---
def get_safe_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            all_models = [m['name'].replace("models/", "") for m in data.get('models', [])]
            safe_models = [m for m in all_models if "gemini" in m and "embedding" not in m and "exp" not in m]
            if any("flash" in m for m in safe_models): return [m for m in safe_models if "flash" in m][0]
            if safe_models: return safe_models[0]
    except:
        pass
    return "gemini-1.5-flash"

# --- GENERATE WITH RETRY ---
def get_ai_reply(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg
    model_name = get_safe_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    for attempt in range(2): 
        try:
            response = requests.post(url, json=payload, timeout=8)
            if response.status_code == 200:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return text
            elif response.status_code in [429, 503]:
                time.sleep(1)
                continue
            else:
                return "Our servers are busy right now. Please try again."
        except:
            time.sleep(1)
    
    return "Our servers are busy right now. Please try again."

# --- MAIN BOT ROUTE ---
@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")
    
    resp = MessagingResponse()
    msg = resp.message()

    # --- 🟢 1. NEW USER? DETECT INTENT & PHONE ---
    if sender_phone not in user_sessions:
        # Auto-capture Phone
        new_session = {
            "step": "ask_name", 
            "data": {
                "wa_number": sender_phone, 
                "phone": sender_phone  # ✅ Auto-Saved!
            },
            "sent_images": [] 
        }
        
        # Smart Product Detection (Did they ask for Sakhitone in 1st msg?)
        user_text_lower = incoming_msg.lower()
        for product_key in PRODUCT_IMAGES.keys():
            if product_key in user_text_lower:
                new_session["data"]["product"] = product_key # ✅ Auto-Saved!
                break
        
        user_sessions[sender_phone] = new_session
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
        return str(resp)

    session = user_sessions[sender_phone]
    step = session["step"]
    
    if "sent_images" not in session: session["sent_images"] = []

    # --- 🟢 2. COLLECT DETAILS (SKIPPING PHONE & PRODUCT IF KNOWN) ---

    if step == "ask_name":
        session["data"]["name"] = incoming_msg
        session["step"] = "ask_age"
        msg.body(f"Nice to meet you, {incoming_msg}. \nMay I know your *Age*?")
        return str(resp)

    elif step == "ask_age":
        session["data"]["age"] = incoming_msg
        session["step"] = "ask_place"
        msg.body("Thank you. Which *Place/District* are you from?")
        return str(resp)

    elif step == "ask_place":
        session["data"]["place"] = incoming_msg
        
        # CHECK: Do we already know the product? (From first message)
        if "product" in session["data"]:
             # SKIP 'Ask Product' step -> Go straight to Answer
            session["step"] = "chat_active"
            product_name = session["data"]["product"]
            save_to_google_sheet(session["data"])
            
            ai_reply = get_ai_reply(f"Tell me about {product_name} benefits ONLY. Do NOT mention Usage or Price. Answer in English and Malayalam.")
            if ai_reply: ai_reply = ai_reply.replace("**", "*")
            
            msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
            
            # Send Image
            if product_name in PRODUCT_IMAGES:
                 msg.media(PRODUCT_IMAGES[product_name])
                 session["sent_images"].append(product_name)
                 
            return str(resp)
        else:
            # We don't know product yet, so ASK it.
            session["step"] = "ask_product"
            msg.body("Noted. Which *Product* do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
            return str(resp)

    # Only used if we didn't auto-detect product
    elif step == "ask_product":
        session["data"]["product"] = incoming_msg
        save_to_google_sheet(session["data"])
        session["step"] = "chat_active" 
        
        ai_reply = get_ai_reply(f"Tell me about {incoming_msg} benefits ONLY. Do NOT mention Usage or Price. Answer in English and Malayalam.")
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 800: ai_reply = ai_reply[:800] + "..."

        msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
        
        user_text_lower = incoming_msg.lower()
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                if key not in session["sent_images"]:
                    msg.media(image_url)
                    session["sent_images"].append(key)
                break
                
        return str(resp)

    # --- 🟢 3. NORMAL CHAT ---
    elif step == "chat_active":
        ai_reply = get_ai_reply(incoming_msg)
        
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 1000: ai_reply = ai_reply[:1000] + "..."
        
        msg.body(ai_reply)
        
        user_text_lower = incoming_msg.lower()
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                if key not in session["sent_images"]:
                    msg.media(image_url)
                    session["sent_images"].append(key)
                break
                
        return str(resp)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
