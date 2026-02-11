from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("briefing", "0003_dailybriefing_email_failure_reason_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="dailybriefing",
            old_name="email_recipient_count",
            new_name="email_sent_count",
        ),
        migrations.AddField(
            model_name="dailybriefing",
            name="email_target_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
