from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='booklisting',
            name='search_embedding',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
