"""
Build a realistic, reproducible training dataset for the scam detector.

The original SMS Spam Collection used to train the production model is no
longer present in the repository, which made the training pipeline
unreproducible. This script generates a diverse, realistic labelled corpus
of ``ham`` (safe) and ``spam`` (scam) SMS/email-style messages in the exact
tab-separated format consumed by ``model/train_final.py``:

    <label>\t<text>

The corpus is built deterministically from curated sentence banks plus a set
of phishing/impersonation templates expanded across realistic surface forms
(no randomness, no network access). It deliberately covers the scam patterns
real users encounter (bank account suspension, prize wins, OTP/security
alerts, tax demands, delivery scams, crypto/romance schemes, etc.) so the
model learns to detect them rather than only classic bulk SMS spam.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "smsspamcollection" / "SMSSpamCollection"

# ---------------------------------------------------------------------------
# Hand-authored, varied SAFE (ham) messages. These represent normal human
# communication and benign notifications so the model does not flag them.
# ---------------------------------------------------------------------------
HAM_SENTENCES = [
    "Hey, are you free this evening? Let's meet tomorrow.",
    "Can you send me the project report before 5 PM?",
    "Thanks for your help with the presentation yesterday.",
    "Reminder: Team standup at 10 AM tomorrow morning.",
    "See you at the cafe at 7.",
    "Happy birthday! Hope you have a great day.",
    "Did you watch the game last night?",
    "I'll be home late tonight, don't wait for me.",
    "Can you pick up milk on the way back?",
    "The meeting is moved to Thursday.",
    "Your OTP is 482913. Do not share it with anyone.",
    "Your order number 12345 has been shipped and will arrive tomorrow.",
    "Mom says dinner is ready.",
    "Are you coming to the party on Saturday?",
    "Let's grab lunch sometime this week.",
    "I finished the assignment, submitting now.",
    "The train is delayed by 10 minutes.",
    "Call me when you get a chance.",
    "Great job on the demo today!",
    "Can we reschedule our call to 3 PM?",
    "The weather looks nice, going for a run.",
    "Thanks for the birthday gift, really appreciate it.",
    "Do you want to watch a movie later?",
    "I left the keys under the mat.",
    "See you at the gym at 6.",
    "Please review the attached document when free.",
    "The kids are asleep now, finally quiet.",
    "What time is the dentist appointment?",
    "Just landed, will text when I get home.",
    "Don't forget to water the plants.",
    "Lunch was delicious, thanks for the recommendation.",
    "Can you forward me the invoice?",
    "I'm stuck in traffic, running 5 mins late.",
    "The book you lent me was amazing.",
    "Weekend plans? Thinking of a hike.",
    "Your appointment is confirmed for Monday at 2 PM.",
    "We should catch up soon, it's been too long.",
    "The wifi password is on the fridge.",
    "Good night, talk tomorrow.",
    "Did the package arrive yet?",
    "Let's book the restaurant for Friday.",
    "The cat knocked over the plant again.",
    "I'll bring snacks to the meeting.",
    "School pick-up is at half past three.",
    "The bill came to twenty three pounds.",
    "Could you proofread my essay?",
    "Traffic is clear on the motorway.",
    "I booked the hotel near the beach.",
    "Remember to lock the back door.",
    "The lecture starts at nine sharp.",
    "We're out of coffee, adding it to the list.",
    "Sent the photos from the trip, check your email.",
    "Practice is cancelled due to rain.",
    "Grandma is feeling much better today.",
    "The new sofa arrives next week.",
    "I'll handle the dishes tonight.",
    "Let me know if you need a lift.",
    "The recipe turned out really well.",
    "Our flight leaves at quarter past six.",
    "The library closes at eight.",
    "Could you save me a seat?",
    "The dog needs a walk before bed.",
    "I'm reading a great novel right now.",
    "The concert was absolutely brilliant.",
    "We're having pasta for dinner.",
    "Text me when you reach the station.",
    "The exam results are out tomorrow.",
    "I'm taking the dog to the vet at noon.",
    "The garden looks lovely this spring.",
    "Can you water the plants while I'm away?",
    "The bus was early for once.",
    "Let's try that new place downtown.",
    "I finished the book, loved the ending.",
    "The baby finally went down for a nap.",
    "We're meeting at the usual spot.",
    "The printer ran out of ink again.",
    "I'll cook dinner if you do the dishes.",
    "The park is open until sunset.",
    "My phone battery is about to die.",
    "The seminar was moved online.",
    "Let's leave by seven to beat traffic.",
    "The cake is in the fridge for the party.",
    "I found your missing earring by the sofa.",
    "The movie starts in twenty minutes.",
    "Could you grab some bread on the way?",
    "The kids finished their homework already.",
    "We should repaint the bedroom this summer.",
    "The neighbour is having a barbecue.",
    "I'll drop the files on your desk tomorrow.",
    "The bus pass needs renewing.",
    "Let's walk along the river this weekend.",
    "The kettle just boiled, tea?",
    "I booked the dentist for next Tuesday.",
    "The scarf you knitted is so warm.",
    "We're short on eggs, can you buy some?",
    "The podcast episode was fascinating.",
    "I'll be in the office until four.",
    "The seedlings are sprouting nicely.",
    "Can you check the oven, please?",
    "The sunset from the hill was stunning.",
    "I'll bring the board game on Friday.",
    "The tyre pressure light came on again.",
    "We're adopting a kitten next month.",
    "The museum has a free entry day.",
    "Let me know what time suits you.",
    "The parcel from mum arrived today.",
    "I'm learning to play the guitar.",
    "The rain cleared just in time.",
    "Could you send me the zoom link?",
    "The laundry is folded and put away.",
    "We're going camping by the lake.",
    "The new colleague seems really nice.",
    "I'll take the late shift on Thursday.",
    "The strawberries this year are sweet.",
    "Let's repot the plants this weekend.",
    "The café on the corner does great coffee.",
    "I'm behind on emails, clearing them now.",
    "The children loved the puppet show.",
    "We're renovating the kitchen next month.",
    "The ferry departs at half past eight.",
    "Could you mind the shop while I step out?",
    "The playlist you made is perfect.",
    "I'll collect the prescriptions after work.",
    "The wind knocked over the bin again.",
    "We're planting tulips in the front garden.",
    "The workshop was very informative.",
    "Let's meet at the library entrance.",
    "The toast is ready, grab yours.",
    "I'm off to the gym, back in an hour.",
    "The puppy slept through the night.",
    "We should visit the aquarium soon.",
    "The letter from the school arrived.",
    "Can you help me move the sofa?",
    "The snow is finally melting.",
    "I'll set the alarm for six.",
    "The choir practice is on Wednesday.",
    "We ran out of milk again, sorry.",
    "The view from the top was worth it.",
    "Let me know if you find my glasses.",
    "The cake sale raised a lot for charity.",
    "I'm taking the train to Edinburgh.",
    "The cat is sleeping in the sunbeam.",
    "We're having a small get-together Sunday.",
    "The doctor's appointment went fine.",
    "Could you pass me the remote?",
    "The sunrise was pink over the fields.",
    "I'll water the garden before work.",
    "The book club meets on the first Monday.",
    "We're getting a new dishwasher.",
    "The baby laughed at the puppet.",
    "Let's bake cookies for the fair.",
    "The traffic cleared after the junction.",
    "I found a great café near the office.",
    "The garden party is still on, rain or shine.",
    "Could you sign this form for me?",
    "The laptop is charging, nearly full.",
    "We're watching the match at mine.",
    "The postman left a card, redelivery booked.",
    "I'll bring extra umbrellas, it's forecast rain.",
    "The choir sang beautifully at the service.",
    "Let's cycle to the coast this summer.",
    "The new phone case fits perfectly.",
    "I'm updating my CV this evening.",
    "The market had lovely fresh veg.",
    "We're tiling the bathroom at the weekend.",
    "The owl was hooting in the woods.",
    "Could you wake me at seven, please?",
    "The roses are in full bloom.",
    "I'll mend the fence after lunch.",
    "The quiz night was great fun.",
    "We're adopting the rescue dog tomorrow.",
    "The sunrise walk was freezing but worth it.",
    "Let me know if you need anything from the shop.",
    "The piano tuner is coming Friday.",
    "I'm sorting the photos into albums.",
    "The bees are loving the lavender.",
    "We're painting the fence this weekend.",
    "The kitten climbed the curtain again.",
    "Could you save the last slice for me?",
    "The river level dropped after the dry spell.",
    "I'll post the letters on my way out.",
    "The new bench in the park is comfy.",
    "We're hosting the family on Sunday.",
    "The scarf matches your coat nicely.",
    "Let's go for a swim after work.",
    "The little one learned to ride a bike.",
    "I'm defrosting the freezer this morning.",
    "The starlings put on a show at dusk.",
    "Could you grab my coat from the car?",
    "The greenhouse is full of tomatoes.",
    "We're fixing the shed roof tomorrow.",
    "The ferry was calm and quick today.",
    "I'll print the tickets now.",
    "The children made cards for grandma.",
]

# ---------------------------------------------------------------------------
# Hand-authored, varied SCAM (spam) messages.
# ---------------------------------------------------------------------------
SPAM_SENTENCES = [
    "Congratulations! You won a $1000 cash prize. Claim now by clicking the link.",
    "URGENT: Your bank account has been suspended. Verify your details immediately.",
    "Your bank account has been compromised. Click here to secure it now.",
    "You have won $1,000,000! Claim your prize now by providing your bank details.",
    "IRS notification: You owe back taxes. Pay now to avoid arrest.",
    "HMRC: You are due a tax refund of £150. Claim it here before it expires.",
    "Your package could not be delivered. Reschedule here using the link provided.",
    "Claim your reward by clicking this link right away.",
    "Dear customer, your card has been blocked. Call the number to unblock it.",
    "Get rich quick with crypto! Invest in Bitcoin now through our exclusive link.",
    "You've been selected for a free iPhone. Click here to claim yours today.",
    "Final notice: Your account will be closed unless you verify your identity.",
    "Win a $1000 cash prize! Text WIN to the shortcode now.",
    "Your Netflix subscription expired. Update your payment details at the link.",
    "Hello, I'm an agent from your bank. Your account needs urgent verification.",
    "Claim your $50 gift card now! Limited time offer, act fast.",
    "Security alert: suspicious login detected. Secure your account through this link.",
    "You are entitled to a refund of $320. Claim it here before the deadline.",
    "Your OTP was requested. If this was not you, call the helpline immediately.",
    "We detected unusual activity. Verify your password now to keep your account safe.",
    "Your account will be locked in 24 hours. Confirm your identity through the link.",
    "Congrats! You're our 100000th visitor. Collect your prize at the website.",
    "Dear user, your payment failed. Update your card information at the link.",
    "Immediate action required: your PIN has been reset. Set a new one now.",
    "You have an unclaimed inheritance of $2400. Reply with your personal details.",
    "This is the courier. Pay a small customs fee to release your parcel via the link.",
    "Your loan of $1200 is approved. Activate it now through our secure portal.",
    "Urgent: your card will be cancelled. Keep it active by confirming here.",
    "Free voucher waiting for you. Click the link before midnight tonight.",
    "Your account is on hold. Verify your billing information through the link.",
    "Lottery winners announced! You won a luxury watch. Claim at the website.",
    "Covid relief fund: you qualify for $750. Apply through the link provided.",
    "Your crypto wallet is at risk. Move your funds to the secure wallet now.",
    "You must pay the outstanding invoice or face legal action. Pay here.",
    "Your SIM was swapped. Secure your bank account now through this link.",
    "Exclusive investment: double your money in 7 days with Ethereum. Click now.",
    "Your statement is ready. View and confirm your details at the link.",
    "Password expiring in 1 hour. Renew it through the provided link.",
    "You've been reported for suspicious activity. Appeal now at the link.",
    "Win a free TV! Only 3 left. Enter your details at the website.",
    "Your rewards points expire today. Redeem them through the link.",
    "Click the link to claim your free gift card before it's gone.",
    "Your PayPal account has been limited. Confirm your information to restore it.",
    "A friend transferred crypto to you. Withdraw it via the link.",
    "Your Amazon order is on hold. Update payment to avoid cancellation.",
    "Verify your email to prevent your account from being deactivated.",
    "You've been chosen for a secret shopper programme. Register at the link.",
    "Your mobile number won a prize. Submit your address to receive it.",
    "Act now: your warranty expires tonight. Extend it through the link.",
    "Your photos are hosted on a private album, view them here.",
    "Confirm your date of birth to keep your account active.",
    "You qualified for a low-interest loan. Apply in minutes via the link.",
    "Your subscription renews at a higher rate. Cancel or keep at the link.",
    "A parcel is waiting, pay the redelivery fee through this link.",
    "Your bank detected a new device. Approve the login through the link.",
    "Claim compensation for your recent flight delay at the website.",
    "Your account shows suspicious transactions. Review them here.",
    "Exclusive: buy Bitcoin cheap before the price rises. Link inside.",
    "Your child's school needs urgent payment for a trip. Pay here.",
    "You've been pre-approved for a credit card. Activate at the link.",
    "Reset your password using the link we sent to keep your data safe.",
    "Your gift is reserved, pay shipping to receive it.",
    "Verify your identity to release the funds held in your name.",
    "Your insurance lapsed. Reinstate it through the link to stay covered.",
    "Click to confirm you are human and keep your account unlocked.",
    "Your tax return has a refund ready. Enter your details to receive it.",
    "Your card was charged twice. Request a refund through the link.",
    "Winners of the monthly draw: you won! Claim your prize here.",
    "Your bank app needs an update. Download it from the link provided.",
    "A relative named you in a will. Contact the lawyer through the link.",
    "Your login was flagged. Secure your account by verifying now.",
    "Free trial ends tomorrow, cancel or pay via the link.",
    "Your electricity bill is overdue. Pay now to avoid disconnection.",
    "You've received a voice message, listen to it at the link.",
    "Confirm your address to receive the parcel we could not deliver.",
    "Your membership is about to expire. Renew at a discount through the link.",
    "Your bank details were changed. If not you, revert via the link.",
    "Claim your cashback reward by entering your card number here.",
    "Your account is flagged for fraud. Verify to unfreeze it.",
    "You're eligible for a government grant. Apply through the link.",
    "Your domain registration expired. Renew it to avoid losing it.",
    "A payment of $499 was attempted. Authorise or cancel at the link.",
    "Your cloud storage is full. Upgrade through the link to keep files.",
    "You matched with a sugar mummy, chat and earn at the link.",
    "Your crypto airdrop is ready, connect your wallet to claim.",
    "Your ticket booking is incomplete. Complete payment via the link.",
    "Verify your phone number to enter the giveaway.",
    "Your bank sent a code, forward it to confirm your identity.",
    "Your account will be deleted in 24 hours unless you verify.",
    "Claim your free bet and double your winnings at the link.",
    "Your prescription is ready, pay the fee to dispatch.",
    "Your TV licence is unpaid, pay now or face prosecution.",
    "You've been selected for a paid survey, register at the link.",
    "Your subscription to the dating site is pending, confirm payment.",
    "Your pension has a bonus, withdraw it through the link.",
    "Your WiFi router needs resetting, use the link to secure it.",
    "You left items in your cart, complete checkout via the link.",
    "Your job application advanced, pay the processing fee here.",
    "Your bank flagged a transfer, approve via the secure link.",
    "Claim your anniversary reward by clicking the link.",
    "Your credit score dropped, fix it through the link.",
    "Your password was found in a breach, change it at the link.",
    "You won a scholarship, pay the admin fee to release it.",
    "Your pet's microchip renewal is due, pay at the link.",
    "Your gym membership is frozen, reactivate via the link.",
    "Your loyalty points convert to cash, redeem at the website.",
    "Your exam results are ready, view them through the link.",
    "Your booking is confirmed only after a small verification payment.",
    "Your account won a voucher, but it expires in one hour.",
    "Your Airbnb guest cancelled, refund via the link.",
    "Your energy supplier overcharged you, claim the refund here.",
    "Your social security number was used, verify to protect it.",
    "Your store card is pre-approved for a limit increase, activate.",
    "Your mail is being held, pay to release it at the link.",
    "Your crypto exchange account is locked, unlock via the link.",
    "You are a winner in the monthly promotion, claim at the website.",
    "Your child's school trip needs consent, pay the deposit here.",
    # --- Tax / IRS / revenue impersonation scams ---
    "IRS notification: You owe back taxes. Pay now to avoid arrest.",
    "Tax office: you have unpaid tax, settle immediately to avoid prosecution.",
    "HMRC: unpaid tax detected on your account, pay now or face penalties.",
    "Inland Revenue: your tax return is overdue, clear the balance today.",
    "You owe back taxes and a warrant is issued. Pay now to avoid arrest.",
    "Federal tax department: final notice, pay the owed amount to prevent legal action.",
    "Revenue service: your refund is blocked until you verify outstanding tax.",
    "IRS: your account is flagged for unpaid taxes, pay within 24 hours.",
    "Tax authority: failure to pay will result in arrest, settle now.",
    "You are being audited and owe taxes, pay the fee to close the case.",
    "Customs and revenue: unpaid duty detected, pay immediately online.",
    "Your tax refund is pending, pay a release fee to receive it.",

    "Your bank statement has unusual charges, review via the link.",
    "Your phone is infected, clean it through the link.",
    "You received a secret admirer message, read it at the link.",
    "Your visa application needs a fee, pay through the portal.",
    "Your parcel is stuck in customs, pay the duty via the link.",
    "Your account qualifies for a refund, enter bank details here.",
    "Your streaming account shared, verify to keep it active.",
    "Your emergency fund is ready, withdraw via the link.",
    "Your name was drawn, collect the prize at the website.",
    "Your insurance quote is ready, but only if you pay a deposit.",
    "Your bank app logged you out, sign in again through the link.",
    "You inherited property abroad, contact the agent via the link.",
    "Your ticket is confirmed after a verification charge.",
    "Your electricity Smart Meter needs a top up, pay at the link.",
    "Your friend tagged you in a photo, view at the link.",
    "Your bank ordered a new card, approve the delivery via the link.",
    "You are owed overtime pay, claim it through the portal.",
    "Your account is being migrated, confirm credentials at the link.",
    "Your free trial converted, cancel with payment at the link.",
    "Your social media account will be banned, appeal via the link.",
    "You qualified for debt relief, apply through the website.",
]

# ---------------------------------------------------------------------------
# Template-based phishing patterns expanded across realistic surface forms.
# These ensure the model sees many ways the same scam theme is phrased.
# ---------------------------------------------------------------------------
BANKS = [
    "bank", "Bank of America", "Chase", "Wells Fargo", "HSBC", "Citibank",
    "Barclays", "NatWest", "Santander", "PayPal", "Netflix", "Amazon",
    "Apple", "Microsoft", "Google", "Meta", "Instagram", "WhatsApp",
    "DPD", "FedEx", "UPS", "Royal Mail", "HMRC", "IRS", "Coinbase",
]
SERVICES = ["Netflix", "Spotify", "Disney+", "iCloud", "Microsoft 365", "Amazon Prime"]
LINKS = [
    "http://bit.ly/3x9k2", "https://secure-verify-account.com",
    "http://ow.ly/acc-update", "https://tinyurl.com/claim-prize",
    "http://free-gift-card.info", "https://account-confirm-now.net",
]
PHONES = ["0800 123 4567", "+1 800 555 0199", "07700 900123", "+44 7700 900 321"]
SHORTCODES = ["87777", "63333", "70007", "85025"]
COINS = ["Bitcoin", "Ethereum", "Dogecoin", "Solana", "BNB"]
PRODUCTS = ["iPhone 15", "£500 voucher", "$1000 Amazon card", "free TV", "holiday"]
PRIZES = ["$1000 cash", "£1000", "a free iPhone", "$1,000,000", "a luxury watch", "an iPad"]
AMOUNTS = ["49", "99", "150", "320", "750", "1200", "2400"]
NAMES = ["David", "Sarah", "James", "Aisha", "Tom", "Emma", "Liam", "Olivia"]
CODES = ["482913", "771204", "309582", "661077", "204815"]

PHISHING_TEMPLATES = [
    "URGENT: Your {bank} account has been suspended. Verify your details at {link}.",
    "Your {bank} account has been compromised. Click here to secure it: {link}",
    "Dear customer, your {bank} card has been blocked. Call {phone} to unblock.",
    "Security alert: suspicious login detected on your {bank} account. Secure it: {link}",
    "We detected unusual activity. Verify your password now: {link}",
    "Your {service} subscription expired. Update payment at {link}",
    "Claim ${amount} gift card now! Limited time only: {link}",
    "Congratulations! You won {prize}. Claim now by clicking {link}.",
    "Your {bank} OTP was requested. If this was not you, call {phone} immediately.",
    "Your {bank} account will be locked soon. Confirm identity: {link}",
    "A refund of ${amount} is pending for your {bank} account. Claim: {link}",
    "Your {service} payment failed. Update card details at {link}",
    "Immediate action: your {bank} PIN was reset. Set a new one: {link}",
    "You have an unclaimed {prize}. Respond with your details to claim.",
    "Package not delivered. Pay {amount} customs to release: {link}",
    "Your {coin} wallet is at risk. Move funds to our secure wallet: {link}",
    "Sir, you owe ${amount} in taxes. Pay now or face legal action: {link}",
    "Your SIM was swapped. Secure your {bank} account now: {link}",
]

HAM_TEMPLATES = [
    "Hi, your {bank} statement is in the post, should arrive Friday.",
    "Reminder: your {service} payment of £{amount} went through fine.",
    "Thanks, I got the OTP and logged in, all sorted.",
    "Can you confirm the {bank} transfer went to the right account?",
    "Your {service} renewal is due next month, please budget for it.",
    "Hi {name}, the {bank} app update looks good, no issues here.",
    "Just paid the {service} bill, thanks for the reminder.",
    "{name} sent the {bank} details, can you double check them?",
    "The {bank} branch is open until six if you need anything.",
    "I updated the {service} password, all working now.",
]


def _fill(tpl: str) -> str:
    return (
        tpl.replace("{bank}", BANKS[0])
        .replace("{service}", SERVICES[0])
        .replace("{link}", LINKS[0])
        .replace("{phone}", PHONES[0])
        .replace("{shortcode}", SHORTCODES[0])
        .replace("{coin}", COINS[0])
        .replace("{product}", PRODUCTS[0])
        .replace("{prize}", PRIZES[0])
        .replace("{amount}", AMOUNTS[0])
        .replace("{name}", NAMES[0])
        .replace("{code}", CODES[0])
    )


def build_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for s in SPAM_SENTENCES:
        rows.append(("spam", s))
    for s in HAM_SENTENCES:
        rows.append(("ham", s))
    # Expand phishing templates across banks / links / phones / coins.
    for tpl in PHISHING_TEMPLATES:
        for bank in BANKS:
            for link in LINKS[:3]:
                for phone in PHONES[:2]:
                    text = (
                        tpl.replace("{bank}", bank)
                        .replace("{service}", SERVICES[0])
                        .replace("{link}", link)
                        .replace("{phone}", phone)
                        .replace("{shortcode}", SHORTCODES[0])
                        .replace("{coin}", COINS[0])
                        .replace("{product}", PRODUCTS[0])
                        .replace("{prize}", PRIZES[0])
                        .replace("{amount}", AMOUNTS[0])
                        .replace("{name}", NAMES[0])
                        .replace("{code}", CODES[0])
                    )
                    rows.append(("spam", text))
    # Expand benign banking/OTP templates across banks / names.
    for tpl in HAM_TEMPLATES:
        for bank in BANKS[:8]:
            for name in NAMES[:4]:
                text = (
                    tpl.replace("{bank}", bank)
                    .replace("{service}", SERVICES[0])
                    .replace("{link}", LINKS[0])
                    .replace("{phone}", PHONES[0])
                    .replace("{shortcode}", SHORTCODES[0])
                    .replace("{coin}", COINS[0])
                    .replace("{product}", PRODUCTS[0])
                    .replace("{prize}", PRIZES[0])
                    .replace("{amount}", AMOUNTS[0])
                    .replace("{name}", name)
                    .replace("{code}", CODES[0])
                )
                rows.append(("ham", text))
    return rows


def main() -> None:
    rows = build_rows()
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for label, text in rows:
        key = (label, text.strip())
        if key not in seen:
            seen.add(key)
            unique.append((label, text.strip()))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for label, text in unique:
            f.write(f"{label}\t{text}\n")
    spam = sum(1 for l, _ in unique if l == "spam")
    ham = sum(1 for l, _ in unique if l == "ham")
    print(f"Wrote {len(unique)} rows ({spam} spam / {ham} ham) to {OUT_PATH}")


if __name__ == "__main__":
    main()
