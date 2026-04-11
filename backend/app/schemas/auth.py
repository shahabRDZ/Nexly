from pydantic import BaseModel, field_validator
import phonenumbers


class PhoneRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            parsed = phonenumbers.parse(v)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except (phonenumbers.NumberParseException, ValueError):
            raise ValueError("Invalid phone number. Use E.164 format, e.g. +14155551234")


class OTPVerify(BaseModel):
    phone: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_new_user: bool
