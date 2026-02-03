from django.db import migrations, models
import django.db.models.deletion


def set_tag_user_from_tasks(apps, schema_editor):
    Tag = apps.get_model('task', 'Tag')
    Task = apps.get_model('task', 'Task')

    through = Task.tags.through

    tag_ids = list(Tag.objects.filter(user__isnull=True).values_list('id', flat=True))
    if not tag_ids:
        return

    for tag_id in tag_ids:
        user_ids = list(
            through.objects.filter(tag_id=tag_id)
            .values_list('task__user_id', flat=True)
            .distinct()
        )
        if len(user_ids) == 1 and user_ids[0]:
            Tag.objects.filter(id=tag_id).update(user_id=user_ids[0])


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_user_sleep_times'),
        ('task', '0006_task_deadline_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='tag',
            name='user',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='user.user'),
        ),
        migrations.RunPython(set_tag_user_from_tasks, migrations.RunPython.noop),
    ]
