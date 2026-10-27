from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class FitClubSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 1.0

    def items(self):
        return ['landing_page', 'home']

    def location(self, item):
        return reverse(item)
