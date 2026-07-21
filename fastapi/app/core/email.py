import resend
from app.core.config import settings

# Set the API key once — resend uses it for all calls
resend.api_key = settings.resend_api_key


async def send_appointment_confirmation_email(
        to_email: str,
        customer_name: str,
        property_title: str,
        appointment_date: str,
        appointment_time: str,
        appointment_id: str,
) -> None:
    """
    Sends appointment confirmation email to the customer.
    Called as a background task — runs after the HTTP response is sent.
    If this fails, the appointment still exists in the database.
    Email failure should NEVER roll back the booking.
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": f"Viewing confirmed — {property_title}",
            "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #1565C0; padding: 24px; text-align: center;">
                        <h1 style="color: white; margin: 0;">🏠 Rongai House Hunters</h1>
                    </div>

                    <div style="padding: 32px;">
                        <h2>Hi {customer_name},</h2>

                        <p>Your viewing appointment has been confirmed!</p>

                        <div style="background: #E3F2FD; border-left: 4px solid #1565C0; 
                                    padding: 16px; margin: 24px 0; border-radius: 4px;">
                            <strong>Property:</strong> {property_title}<br>
                            <strong>Date:</strong> {appointment_date}<br>
                            <strong>Time:</strong> {appointment_time}
                        </div>

                        <p>
                            <strong>Important:</strong> The caretaker will give you a 
                            4-digit viewing code when you arrive. Enter this code in the 
                            app to confirm you attended the viewing.
                        </p>

                        <p style="color: #C62828;">
                            ⚠️ Never pay any deposit before physically viewing the house.
                        </p>

                        <a href="https://rongai-house-finder.vercel.app/dashboard/customer/appointments/{appointment_id}"
                           style="background: #1565C0; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            View Appointment Details
                        </a>
                    </div>

                    <div style="background: #F5F5F5; padding: 16px; text-align: center; 
                                color: #757575; font-size: 12px;">
                        © 2026 Rongai House Hunters
                    </div>
                </div>
            """,
        })
    except Exception as e:
        # Log the error but DO NOT raise it
        # A failed email must never crash the API or reverse the booking
        print(f"Email send failed for appointment {appointment_id}: {e}")


async def send_signup_welcome_email(
        to_email: str,
        full_name: str,
        role: str,
) -> None:
    """
    Sends a welcome email when a new user signs up.
    Called as a background task from the signup endpoint.
    """
    role_message = (
        "Start browsing verified houses in Rongai."
        if role == "customer"
        else "Your account is under review. We'll email you within 1–2 business days."
    )

    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": "Welcome to Rongai House Hunters 🏠",
            "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #1565C0; padding: 24px; text-align: center;">
                        <h1 style="color: white; margin: 0;">🏠 Rongai House Hunters</h1>
                    </div>
                    <div style="padding: 32px;">
                        <h2>Welcome, {full_name}!</h2>
                        <p>Your account has been created successfully.</p>
                        <p>{role_message}</p>
                        <a href="https://rongai-house-finder.vercel.app"
                           style="background: #1565C0; color: white; padding: 12px 24px;
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            Open Rongai House Hunters
                        </a>
                    </div>
                </div>
            """,
        })
    except Exception as e:
        print(f"Welcome email failed for {to_email}: {e}")