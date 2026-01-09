from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
import json
from .models import Product, Entry

User = get_user_model()


class ViewsAjaxTests(TestCase):
    """
    Testu klase, kas pārbauda AJAX/JSON endpointus skata līmenī.

    Šeit tiek testēts:
    - `api_add_entry` — vai JSON payload izveido Entry ierakstu pieslēgtajam lietotājam,
    - `edit_entry` — vai ieraksta grozīšana ar JSON strādā un atjauno vērtības,
    - `delete_entry` — vai dzēšana atgriež success un ieraksts tiek izdzēsts,
    - Bezpilnvarota piekļuve — vai mēģinājums rediģēt cita lietotāja ierakstu atgriež 403.
    """

    def setUp(self):
        # Izveido divus lietotājus un testprodukts; pieslēdz klientu par `self.user`.
        self.user = User.objects.create_user(username='tester', email='t@example.com', password='pw')
        self.other = User.objects.create_user(username='other', email='o@example.com', password='pw')
        self.product = Product.objects.create(name='TestProduct', calories_per_100g=200, protein_per_100g=5, fat_per_100g=3, carbs_per_100g=20)
        self.client.force_login(self.user)

    def test_api_add_entry_json(self):
        # Nosūta JSON uz api_add_entry un pārbauda, ka ieraksts izveidots DB
        url = reverse('nutrition:api_add_entry')
        payload = {
            'name': 'MyCustom',
            'amount': 120,
            'kcal': 240.0,
            'protein': 6.0,
            'fat': 3.6,
            'carbs': 24.0,
        }
        resp = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        # Sagaida 200 OK un success True
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        # Pārliecinās, ka Entry ar nosaukumu un lietotāju ir saglabāts
        self.assertTrue(Entry.objects.filter(user=self.user, name='MyCustom').exists())

    def test_edit_entry_json(self):
        # Izveido pielāgotu Entry un nosūta JSON izmaiņām (samazina daudzumu)
        e = Entry.objects.create(user=self.user, name='ToEdit', amount=100, kcal=200, protein=10, fat=5, carbs=20)
        url = reverse('nutrition:edit_entry', args=[e.pk])
        resp = self.client.post(url, data=json.dumps({'amount': 50}), content_type='application/json')
        # Sagaida, ka atgrieztais rezultāts paziņo par veiksmīgu atjaunināšanu
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        e.refresh_from_db()
        # Pārliecinās, ka amount patiešām tika nomainīts uz 50
        self.assertEqual(e.amount, 50)

    def test_delete_entry_json(self):
        # Izveido Entry, tad dzēš to izmantojot JSON POST uz delete_entry
        e = Entry.objects.create(user=self.user, name='ToDelete', amount=100, kcal=200, protein=10, fat=5, carbs=20)
        url = reverse('nutrition:delete_entry', args=[e.pk])
        resp = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        # Pārbauda, ka ieraksts vairs neeksistē
        self.assertFalse(Entry.objects.filter(pk=e.pk).exists())

    def test_edit_other_entry_forbidden(self):
        # Pārbauda, ka nevar rediģēt cita lietotāja Entry — sagaida 403
        e = Entry.objects.create(user=self.other, name='OtherEntry', amount=100, kcal=200, protein=10, fat=5, carbs=20)
        url = reverse('nutrition:edit_entry', args=[e.pk])
        resp = self.client.post(url, data=json.dumps({'amount': 10}), content_type='application/json')
        # Ja lietotājs nav ieraksta īpašnieks, vajadzētu saņemt 403 Forbidden
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        # Un JSON norāda, ka success nav True
        self.assertFalse(data.get('success'))
