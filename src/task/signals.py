from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .models import Task, Subtask
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from domain.schemas.task.main import TaskRetrieveDTO

def send_task_update(task_instance, action="update"):
    if not task_instance or not task_instance.user:
        return

    channel_layer = get_channel_layer()
    
    try:
        # Pydantic's from_attributes works with ORM objects, but accessing related fields (M2M) 
        # triggers queries. Since signals are sync, this is fine.
        task_data = TaskRetrieveDTO.model_validate(task_instance).model_dump(mode='json')
        
        message = {
            "type": "task_update",
            "action": action,
            "task": task_data
        }

        print(f"Sending WS update for user {task_instance.user.id}: {action}") # LOGGING

        async_to_sync(channel_layer.group_send)(
            f"user_{task_instance.user.id}",
            {
                "type": "task_update",
                "message": message
            }
        )
    except Exception as e:
        print(f"Error sending websocket update: {e}")

@receiver(post_save, sender=Task)
def task_post_save(sender, instance, created, **kwargs):
    send_task_update(instance, action="create" if created else "update")

@receiver(m2m_changed, sender=Task.tags.through)
def task_tags_changed(sender, instance, action, **kwargs):
    # Only trigger on post actions to ensure data is in DB
    if action.startswith("post_"):
        send_task_update(instance, action="update")

@receiver(post_save, sender=Subtask)
def subtask_post_save(sender, instance, created, **kwargs):
    # When a subtask is updated/created, update the parent task
    if instance.task:
        send_task_update(instance.task, action="update")

@receiver(post_delete, sender=Subtask)
def subtask_post_delete(sender, instance, **kwargs):
    if instance.task:
        send_task_update(instance.task, action="update")

