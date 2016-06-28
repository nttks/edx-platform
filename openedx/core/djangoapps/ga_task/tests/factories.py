
import json
import uuid

import factory
from factory.django import DjangoModelFactory

from student.tests.factories import UserFactory

from openedx.core.djangoapps.ga_task.models import Task, QUEUING


class TaskFactory(DjangoModelFactory):
    FACTORY_FOR = Task

    task_type = 'dummy_task'
    task_input = json.dumps({})
    task_key = None
    task_id = str(uuid.uuid4())
    task_state = QUEUING
    task_output = None
    requester = factory.SubFactory(UserFactory)
