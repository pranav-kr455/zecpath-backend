import time
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import JobApplication, AICallTracking, AIInterviewSession, AIQuestion, AIAnswer, AICallLog,AIInterviewSchedule
from .utils import evaluate_call_eligibility
from .services import AIVoiceBridgeService, AIScreeningFlowManager, AIAnswerEvaluationEngine

from datetime import timedelta
from .models import AIInterviewSchedule, AIReminderLog
from .services import AIReminderMessagingSystem


@shared_task
def async_dispatch_workflow_email(candidate_email, candidate_name, job_title, status_action):
    """📬 Task 1: Asynchronous email delivery to prevent view controller blocking."""
    print(f"[Celery Worker] Starting email assembly pipeline for {candidate_email}...")
    time.sleep(3)  # Simulating network transmission delays
    
    subject = f"Update regarding your application for {job_title}"
    message = f"Hello {candidate_name},\n\nYour profile status has updated to: {status_action}."
    
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'careers@zecpath.com'),
        recipient_list=[candidate_email],
        fail_silently=False,
    )
    print(f"[Celery Worker] Email successfully delivered to {candidate_email}.")
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_scheduled_voice_ai_trigger(self, application_id):
    """
    📞 Task 2 (Day 37 Optimized): Adaptive Voice Architecture & Quantitative Scoring Engine.
    Runs raw speech text through the AI Evaluation Engine to compute multi-dimensional 
    weighted scores (relevance, completeness, keywords) and normalizes results to the DB.
    """
    try:
        application = JobApplication.objects.get(id=application_id)
        tracking, _ = AICallTracking.objects.get_or_create(application=application)
        tracking.last_attempt = timezone.now()
        tracking.status = 'IN_PROGRESS'
        tracking.save()

        # 1. INITIALIZE INFRASTRUCTURE LINKS & SERVICE HANDSHAKES
        ai_bridge = AIVoiceBridgeService()
        candidate_phone = "+919876543210" # In prod, maps to request.user.candidate_profile.phone
        
        success, carrier_receipt = ai_bridge.trigger_outbound_carrier_dial(
            phone_number=candidate_phone,
            application_id=application.id,
            target_language="en-IN"
        )

        if not success:
            raise Exception(carrier_receipt.get("error", "Network connection aborted by carrier gateway."))

        # 2. CREATE SYSTEM ARCHIVAL DATABASE RECORDS
        session = AIInterviewSession.objects.create(application=application, status='CONNECTED')
        AICallLog.objects.create(
            session=session,
            provider_call_sid=carrier_receipt["carrier_sid"],
            telephony_provider="Twilio / Automated Carrier Vapi Trunks",
            sip_response_code=carrier_receipt["http_status_code"],
            trigger_reason=f"Day 37 Scoring Engine: Active evaluation profile matching score ({application.ats_score}%)."
        )

        print(f"[Scoring Engine Pipeline] Session {session.id} initialized. Processing dialogues...")

        # 3. RUN DIALOGUE TURN 1: Initial Ingestion Node
        node_1 = AIScreeningFlowManager.resolve_next_question(session, application)
        q1 = AIQuestion.objects.create(
            session=session,
            question_key=node_1["key"],
            question_text=node_1["text"],
            sequence_order=1
        )
        AIAnswer.objects.create(
            question=q1,
            raw_speech_text="I am currently transitioning into this space, searching for my first job and do not have active corporate developer years yet.",
            confidence_score=0.96,
            structured_analysis={"experience_years": 0} 
        )

        # 4. RUN DIALOGUE TURN 2: Ingestion & Live Answer Scoring Execution Layer
        node_2 = AIScreeningFlowManager.resolve_next_question(session, application)
        q2 = AIQuestion.objects.create(
            session=session,
            question_key=node_2["key"],
            question_text=node_2["text"],
            sequence_order=2
        )
        
        candidate_speech = "I developed Lumina Showcase, a web app connecting a React frontend with Django endpoints."
        target_keys = ["Lumina Showcase", "React", "Django"]
        
        # 💥 Day 37 Core Processing: Fire the decision scoring engine matrix
        scores = AIAnswerEvaluationEngine.evaluate_and_score_text(
            raw_text=candidate_speech,
            required_keywords=target_keys
        )

        AIAnswer.objects.create(
            question=q2,
            raw_speech_text=candidate_speech,
            confidence_score=0.98,
            relevance_score=scores["relevance"],
            completeness_score=scores["completeness"],
            keyword_score=scores["keyword"],
            final_evaluation_score=scores["final_score"],
            structured_analysis={
                "matched_keywords_list": scores["matched_keywords"],
                "system_annotations": scores["annotations"],
                "technical_accuracy_class": "HIGH"
            }
        )

        # 5. CONCATENATE MASTER TRANSCRIPTS AND LOCK SESSION DATA
        session.raw_full_transcript = (
            f"AI System: {q1.question_text}\nCandidate: {q1.answer.raw_speech_text}\n\n"
            f"AI System: {q2.question_text}\nCandidate: {q2.answer.raw_speech_text}\n"
        )
        session.status = 'COMPLETED'
        session.ended_at = timezone.now()
        session.duration_seconds = 105
        session.save()

        # Finalize background metrics records
        tracking.status = 'COMPLETED'
        tracking.execution_logs += f"\n[{timezone.now()}] Scoring metric pipelines successfully logged. Evaluation synchronized."
        tracking.save()

        print(f"[Scoring Engine Task] Complete. Metrics persisted for Session {session.id}.")
        return f"Scoring_Engine_Execution_Successful_Session_{session.id}"

    except Exception as exc:
        tracking = AICallTracking.objects.filter(application_id=application_id).first()
        if tracking:
            tracking.status = 'FAILED'
            tracking.execution_logs += f"\n[{timezone.now()}] Evaluation Ingestion Collapse: {str(exc)}."
            tracking.save()
        raise self.retry(exc=exc)
    
@shared_task
def async_dispatch_scheduling_confirmation_email(schedule_id):
    """📬 Day 38: Asynchronously delivers clean calendar invite and confirmation details."""
    try:
        schedule = AIInterviewSchedule.objects.get(id=schedule_id)
        app = schedule.application
        
        # 👇 SAFE SCAN FALLBACKS
        candidate = "Applicant"
        email = "candidate@zecpath.com"
        
        if hasattr(app, 'candidate') and app.candidate:
            candidate = getattr(app.candidate, 'full_name', 'Applicant')
            # Check user relation through the candidate profile layer
            user_obj = getattr(app.candidate, 'user', None)
            if user_obj:
                email = user_obj.email
        elif hasattr(app, 'candidate_email'):
            email = app.candidate_email

        time_str = schedule.availability_slot.start_time.strftime('%A, %B %d at %I:%M %p (IST)')
        interviewer = schedule.availability_slot.interviewer_name

        print(f"[Scheduling Queue] Dispensing transactional calendar details to {email}...")
        time.sleep(2)

        subject = "Interview Confirmed! - Technical Interview Round"
        message = (
            f"Hello {candidate},\n\n"
            f"Great news! Your next technical evaluation round has been successfully booked.\n\n"
            f"🗓️ Date & Time: {time_str}\n"
            f"👤 Panel Interviewer: {interviewer}\n\n"
            f"Please make sure you are online 5 minutes before your slot begins. Good luck!"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'careers@zecpath.com'),
            recipient_list=[email],
            fail_silently=False
        )
        print(f"[Scheduling Queue] Transaction email successfully delivered to {email}.")
        return True
    except Exception as err:
        print(f"[Scheduling Queue] Notification dispatch failed: {str(err)}")
        return False
    


@shared_task
def execute_periodic_interview_reminder_scan():
    """
    ⏰ Cron Job Simulation: Scans upcoming schedules within critical 24-hour and 1-hour 
    time horizons, evaluates tracking logs, and handles retries gracefully.
    """
    now = timezone.now()
    # Query confirmed upcoming sessions scheduled within the next 25 hours
    upcoming_interviews = AIInterviewSchedule.objects.filter(
        status='CONFIRMED',
        availability_slot__start_time__gte=now,
        availability_slot__start_time__lte=now + timedelta(hours=25)
    )

    processed_logs = []
    print(f"[Reminder Cron] Running automated scan engine loop. Found {upcoming_interviews.count()} candidate blocks...")

    for interview in upcoming_interviews:
        slot = interview.availability_slot
        start_time = slot.start_time
        time_delta = start_time - now
        
        # Pull candidate data fallback variables safely
        app = interview.application
        candidate_name = "Applicant"
        candidate_email = "candidate@zecpath.com"
        
        if hasattr(app, 'candidate') and app.candidate:
            candidate_name = getattr(app.candidate, 'full_name', 'Applicant')
            if getattr(app.candidate, 'user', None):
                candidate_email = app.candidate.user.email
        elif hasattr(app, 'candidate_email'):
            candidate_email = app.candidate_email

        time_display = start_time.strftime('%I:%M %p (IST)')
        
        # ---- STAGE 1: THE 24-HOUR REMINDER GATE ----
        if timedelta(hours=23) <= time_delta <= timedelta(hours=25):
            stage_key = '24_HOUR'
            # Check if this reminder phase has already been run for this interview block
            already_sent = AIReminderLog.objects.filter(interview_schedule=interview, reminder_stage=stage_key).exists()
            
            if not already_sent:
                try:
                    AIReminderMessagingSystem.send_email_reminder(
                        candidate_name, candidate_email, time_display, slot.interviewer_name, stage_key
                    )
                    AIReminderLog.objects.create(interview_schedule=interview, reminder_stage=stage_key, status='SUCCESS')
                    processed_logs.append(f"Dispatched Stage [{stage_key}] for Schedule ID {interview.id}")
                except Exception as e:
                    AIReminderLog.objects.create(interview_schedule=interview, reminder_stage=stage_key, status='FAILED', error_details=str(e))

        # ---- STAGE 2: THE 1-HOUR CRITICAL ALERT GATE ----
        elif time_delta <= timedelta(hours=1.5):
            stage_key = '1_HOUR'
            already_sent = AIReminderLog.objects.filter(interview_schedule=interview, reminder_stage=stage_key).exists()
            
            if not already_sent:
                try:
                    # Trigger both the transaction notification text and the live telephony voice reminder
                    AIReminderMessagingSystem.send_email_reminder(
                        candidate_name, candidate_email, time_display, slot.interviewer_name, stage_key
                    )
                    AIReminderMessagingSystem.trigger_voice_reminder_hook(
                        phone_number="+919876543210", candidate_name=candidate_name, time_str=time_display
                    )
                    AIReminderLog.objects.create(interview_schedule=interview, reminder_stage=stage_key, status='SUCCESS')
                    processed_logs.append(f"Dispatched Critical Stage [{stage_key}] for Schedule ID {interview.id}")
                except Exception as e:
                    AIReminderLog.objects.create(interview_schedule=interview, reminder_stage=stage_key, status='FAILED', error_details=str(e))

    return {"status": "COMPLETE", "actions_executed": processed_logs, "total_scanned": upcoming_interviews.count()}    