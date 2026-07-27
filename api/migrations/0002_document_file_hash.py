from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="file_hash",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
