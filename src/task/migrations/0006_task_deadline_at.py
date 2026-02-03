from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0005_taskhistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='deadline_at',
            field=models.DateTimeField(default=None, null=True),
        ),
    ]

