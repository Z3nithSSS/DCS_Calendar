# Generated by Django 4.2.6 on 2023-12-05 20:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calendarapp', '0005_team_eventmember_team'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='eventmember',
            unique_together={('event', 'team', 'role')},
        ),
    ]
