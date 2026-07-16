import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import create_password_reset_token, verify_password, get_password_hash
from app.models.user import User
from app.api.v1.endpoints.auth import forgot_password, reset_password
from app.schemas.user import PasswordReset, PasswordResetConfirm

async def test_flow():
    email = "user@gmail.com"
    new_password = "updatedPassword123"

    print("--- 1. Testing Forgot Password Endpoint Logic ---")
    async with AsyncSessionLocal() as session:
        payload_forgot = PasswordReset(email=email)
        # Call the endpoint directly
        res_forgot = await forgot_password(payload_forgot, db=session)
        print(f"Forgot password response: {res_forgot}")
        
    print("\n--- 2. Generating Token & Testing Reset Password Endpoint Logic ---")
    token = create_password_reset_token(email)
    print(f"Generated token: {token}")

    async with AsyncSessionLocal() as session:
        payload_reset = PasswordResetConfirm(token=token, new_password=new_password)
        # Call the endpoint directly
        res_reset = await reset_password(payload_reset, db=session)
        print(f"Reset password response: {res_reset}")
        await session.commit()

    print("\n--- 3. Verifying Updated Password in DB ---")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        assert user is not None
        # Verify the new password hash is valid
        is_valid = verify_password(new_password, user.password_hash)
        print(f"Password updated successfully in database: {is_valid}")
        
        # Reset back to original password for development convenience
        user.password_hash = get_password_hash("user123")
        session.add(user)
        await session.commit()
        print("Reverted password back to 'user123' for local dev.")

if __name__ == "__main__":
    asyncio.run(test_flow())
