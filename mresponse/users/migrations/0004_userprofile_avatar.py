# Generated by Django 2.1.2 on 2018-10-30 14:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_userprofile_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar',
            field=models.CharField(default='', max_length=500),
            preserve_default=False,
        ),
    ]
