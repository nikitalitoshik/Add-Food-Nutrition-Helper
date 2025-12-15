from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
import json
from .models import Product, Entry

User = get_user_model()

class ViewsAjaxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='t@example.com', password='pw')
        self.other = User.objects.create_user(username='other', email='o@example.com', password='pw')
        self.product = Product.objects.create(name='TestProduct', calories_per_100g=200, protein_per_100g=5, fat_per_100g=3, carbs_per_100g=20)
        self.client.force_login(self.user)

    def test_api_add_entry_json(self):
        url = reverse('nutrition:api_add_entry')
        payload = {
            'name': 'MyCustom',
            'amount': 120,
            'kcal': 240.0,
            'protein': 6.0,
            'fat': 3.6,
            'carbs': 24.0
        }
        resp = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertTrue(Entry.objects.filter(user=self.user, name='MyCustom').exists())

    def test_edit_entry_json(self):
        e = Entry.objects.create(user=self.user, name='ToEdit', amount=100, kcal=200, protein=10, fat=5, carbs=20)
        url = reverse('nutrition:edit_entry', args=[e.pk])
        resp = self.client.post(url, data=json.dumps({'amount':50}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        e.refresh_from_db()
        self.assertEqual(e.amount, 50)

    def test_delete_entry_json(self):
        e = Entry.objects.create(user=self.user, name='ToDelete', amount=100, kcal=200, protein=10, fat=5, carbs=20)
        url = reverse('nutrition:delete_entry', args=[e.pk])
        resp = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertFalse(Entry.objects.filter(pk=e.pk).exists())

    def test_edit_other_entry_forbidden(self):
        e = Entry.objects.create(user=self.other, name='OtherEntry', amount=100, kcal=200, protein=10, fat=5, carbs=20)
        url = reverse('nutrition:edit_entry', args=[e.pk])
        resp = self.client.post(url, data=json.dumps({'amount':10}), content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data.get('success'))
