from django.core.mail import send_mail
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

def dispatch_workflow_notification(candidate_name, job_title, status_action, candidate_email):
    """
    Day 27: Automated SaaS Communication System parsing dynamic messaging matrices
    and printing live tracking payloads directly to the execution pipeline.
    """
    # 1. Dynamic Dynamic HTML Template System Mapping
    if status_action == "SHORTLISTED":
        subject = f"🎉 Good News! Application Update: {job_title} at ZecPath"
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #0f766e;">Hello {candidate_name},</h2>
                    <p>Congratulations! Our automated screening engine evaluated your resume for the <strong>{job_title}</strong> position and marked your profile as highly compatible.</p>
                    <p>Our talent acquisition team will reach out shortly to coordinate your technical interview rounds.</p>
                    <br>
                    <p>Best regards,<br><strong>ZecPath Talent Acquisition Team</strong></p>
                </div>
            </body>
        </html>
        """
    elif status_action == "REJECTED":
        subject = f"Application Update: {job_title} at ZecPath"
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px;">
                    <h2>Hello {candidate_name},</h2>
                    <p>Thank you for applying to the <strong>{job_title}</strong> role at ZecPath.</p>
                    <p>While your technical skills are impressive, we have chosen to move forward with candidates whose backgrounds align more closely with our current specialized project requirements.</p>
                    <p>We will retain your profile in our talent pool for future engineering updates.</p>
                    <br>
                    <p>Best regards,<br><strong>ZecPath Careers</strong></p>
                </div>
            </body>
        </html>
        """
    else:
        return False

    # 2. Extract Plain Text Fallback for Email Clients
    plain_message = strip_tags(html_message)

    try:
        # 3. Core Dispatch Event Hook
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,  # Automatically falls back to DEFAULT_FROM_EMAIL
            recipient_list=[candidate_email],
            html_message=html_message,
            fail_silently=False,
        )
        # 4. Message Logs Logging
        logger.info(f"✨ Day 27 Communication Success: Dispatched {status_action} notification to {candidate_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Day 27 Delivery Failure for {candidate_email}: {str(e)}")
        return False