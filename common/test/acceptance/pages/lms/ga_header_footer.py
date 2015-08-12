"""
Header and footer page.
"""

from bok_choy.page_object import PageObject


class HeaderPage(PageObject):
    """
    Header page.
    """

    url = None

    def is_browser_on_page(self):
        return self.q(css='header.global').present

    @property
    def logo_link(self):
        return self.q(css='h1.logo a').attrs('href')[0]

    @property
    def navigation_menu_links(self):
        return self.q(css='header ol.user li ul li a').attrs('href')


class FooterPage(PageObject):
    """
    Footer page.
    """

    url = None

    def is_browser_on_page(self):
        return self.q(css='#footer-openedx').present

    @property
    def blog_link(self):
        return self.q(css='#gacco-blog a').attrs('href')[0]

    def get_navigation_link(self, class_name):
        """
        Returns the url of navigation link by specified class name.
        """
        return self.q(css='#footer-openedx nav.nav-colophon .{} a'.format(class_name)).attrs('href')[0]
