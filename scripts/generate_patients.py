import csv
import random

first_names = [
    "Ahmed","Mohamed","Omar","Youssef","Ali","Mariam","Sara","Nour",
    "Laila","Hassan","Mostafa","Aya","Salma","Karim","Hana","Mahmoud",
    "Farah","Nada","Amr","Khaled"
]

last_names = [
    "Ali","Hassan","Ibrahim","Mahmoud","Adel","Nabil","Fathy","Samir",
    "Tarek","Yassin","Kamel","Mostafa","Saleh","Hamdy","Saad","Gaber"
]

genders = ["Male", "Female"]

cities = [
    "Cairo",
    "Giza",
    "Alexandria",
    "Mansoura",
    "Tanta",
    "Zagazig",
    "Ismailia",
    "Assiut"
]

with open("../data/patients.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow([
        "id",
        "first_name",
        "last_name",
        "gender",
        "age",
        "phone",
        "email",
        "city"
    ])

    for i in range(1, 101):

        first = random.choice(first_names)
        last = random.choice(last_names)

        gender = random.choice(genders)

        age = random.randint(18, 70)

        phone = f"TEST-{i:04d}"

        email = f"{first.lower()}.{last.lower()}{i}@example.com"

        city = random.choice(cities)

        writer.writerow([
            i,
            first,
            last,
            gender,
            age,
            phone,
            email,
            city
        ])

print("patients.csv generated successfully!")
