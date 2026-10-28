def validate_phone_number(phone_number):
    valid_phone_number = phone_number[0] == '0' and len(phone_number) == 12 or phone_number[0:2] == '62' and len(phone_number) == 13

    if (not valid_phone_number):
        return "ERROR: nomor telepon harus merupakan nomor telepon Indonesia (diawali prefiks 0-... atau 62-....) dan memiliki 11 digit (tidak termasuk prefix)."
    else:
        return "SUCCESS: Nomor telepon sudah benar."

print(validate_phone_number("081528969321"))
print(validate_phone_number("0815289693213"))
print(validate_phone_number("6281528969321"))
print(validate_phone_number("62815289693212"))
print(validate_phone_number("381528969321"))