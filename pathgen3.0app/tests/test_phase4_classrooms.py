from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.classrooms.models import Classroom, StudentMembership
from apps.classrooms.services import (
    add_student,
    archive_classroom,
    assign_teacher,
    create_classroom,
    reactivate_classroom,
    remove_student,
    update_classroom,
)
from apps.core.models import AuditEvent
from tests.factories import make_classroom, make_membership, make_user


class ClassroomLifecycleTests(TestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN)
        self.teacher = make_user(User.Role.TEACHER)
        self.other_teacher = make_user(User.Role.TEACHER)
        self.student = make_user(User.Role.STUDENT)

    def test_complete_reversible_lifecycle_is_audited(self):
        classroom = create_classroom(actor=self.admin, code="7-A", name="Grade 7 A")
        update_classroom(
            actor=self.admin,
            classroom_id=classroom.pk,
            code="7-A",
            name="Grade 7 Aurora",
        )
        assign_teacher(
            actor=self.admin,
            classroom_id=classroom.pk,
            teacher=self.teacher,
        )
        membership = add_student(
            actor=self.admin,
            classroom_id=classroom.pk,
            student=self.student,
        )
        remove_student(actor=self.admin, membership_id=membership.pk)
        archive_classroom(
            actor=self.admin,
            classroom_id=classroom.pk,
            reason="School year closed",
        )
        reactivate_classroom(actor=self.admin, classroom_id=classroom.pk)

        classroom.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(classroom.name, "Grade 7 Aurora")
        self.assertEqual(classroom.teacher, self.teacher)
        self.assertEqual(classroom.status, Classroom.Status.ACTIVE)
        self.assertIsNotNone(membership.left_at)
        self.assertEqual(membership.removed_by, self.admin)
        self.assertEqual(
            set(AuditEvent.objects.filter(target_id=classroom.pk).values_list("action", flat=True)),
            {
                "classroom.created",
                "classroom.updated",
                "classroom.teacher_assigned",
                "classroom.student_added",
                "classroom.student_removed",
                "classroom.archived",
                "classroom.reactivated",
            },
        )
        self.client.force_login(self.admin)
        invalid = self.client.post(
            reverse("portal:update_class", args=[classroom.pk]),
            {"code": "", "name": classroom.name},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(
            invalid,
            f'aria-describedby="class-code-{classroom.pk}-error"',
            status_code=400,
        )
        self.assertContains(invalid, "This field is required.", status_code=400)

    def test_assigning_another_teacher_replaces_the_single_current_teacher(self):
        classroom = make_classroom()
        assign_teacher(actor=self.admin, classroom_id=classroom.pk, teacher=self.teacher)
        assign_teacher(
            actor=self.admin,
            classroom_id=classroom.pk,
            teacher=self.other_teacher,
        )
        classroom.refresh_from_db()
        self.assertEqual(classroom.teacher, self.other_teacher)

    def test_membership_never_gates_student_learning_access(self):
        self.client.force_login(self.student)
        dashboard = reverse("account:student_dashboard")
        self.assertEqual(self.client.get(dashboard).status_code, 200)

        classroom = make_classroom()
        membership = add_student(
            actor=self.admin,
            classroom_id=classroom.pk,
            student=self.student,
        )
        self.assertEqual(self.client.get(dashboard).status_code, 200)
        remove_student(actor=self.admin, membership_id=membership.pk)
        self.assertEqual(self.client.get(dashboard).status_code, 200)

    def test_teacher_mutation_is_denied_and_reassignment_revokes_scope(self):
        classroom = make_classroom(teacher=self.teacher)
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("portal:update_class", args=[classroom.pk]),
            {"code": "NO", "name": "Forbidden"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.get(reverse("portal:class_detail", args=[classroom.pk])).status_code,
            200,
        )

        assign_teacher(
            actor=self.admin,
            classroom_id=classroom.pk,
            teacher=self.other_teacher,
        )
        self.assertEqual(
            self.client.get(reverse("portal:class_detail", args=[classroom.pk])).status_code,
            404,
        )

    def test_shared_class_detail_preserves_admin_and_teacher_scope(self):
        classroom = make_classroom(teacher=self.teacher)
        archived = make_classroom(teacher=self.teacher, status=Classroom.Status.ARCHIVED)
        url = reverse("portal:class_detail", args=[classroom.pk])
        archived_url = reverse("portal:class_detail", args=[archived.pk])

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(archived_url).status_code, 200)

        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(archived_url).status_code, 404)

        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_removal_closes_membership_instead_of_deleting_it(self):
        classroom = make_classroom()
        membership = make_membership(classroom, self.student, self.admin)
        remove_student(actor=self.admin, membership_id=membership.pk)
        self.assertTrue(StudentMembership.objects.filter(pk=membership.pk).exists())
