from django.db import migrations


def adopt_sample_lookup(apps, schema_editor):
    Policy = apps.get_model('academics', 'ReportPolicy')
    legacy = [
        {'minimum': 80, 'grade': 'A', 'description': 'Excellent'},
        {'minimum': 70, 'grade': 'B', 'description': 'Very good'},
        {'minimum': 60, 'grade': 'C', 'description': 'Good'},
        {'minimum': 50, 'grade': 'D', 'description': 'Satisfactory'},
        {'minimum': 40, 'grade': 'E', 'description': 'Needs improvement'},
        {'minimum': 0, 'grade': 'F', 'description': 'Needs support'},
    ]
    policy = Policy.objects.using(schema_editor.connection.alias).filter(pk=1).first()
    # Preserve approved custom policies and every stored report snapshot.
    if policy and policy.bands == legacy:
        policy.bands = [
            {'minimum': minimum, 'grade': grade, 'description': description}
            for minimum, grade, description in [
                (90, 'A*', 'Excellent'), (85, 'A', 'Super'), (80, 'B+', 'Keep It Up'),
                (75, 'B', 'Very Good'), (70, 'C+', 'Good Work'), (65, 'C', 'Much Better'),
                (60, 'D+', 'Good'), (55, 'D', 'Fair'), (40, 'E', 'Try Harder'),
                (30, 'F', 'Try Harder'), (20, 'G', 'Put More Effort'),
                (10, 'H', 'Work Hard'), (0, 'U', 'Work Hard'),
            ]
        ]
        if policy.heading == 'Quarterly student report':
            policy.heading = 'Performance report'
        policy.revision += 1
        policy.save(update_fields=['bands', 'heading', 'revision'])


class Migration(migrations.Migration):
    dependencies = [('academics', '0002_academicsubject_code_and_more')]
    operations = [migrations.RunPython(adopt_sample_lookup, migrations.RunPython.noop)]
