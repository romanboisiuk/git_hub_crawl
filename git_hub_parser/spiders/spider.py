from random import choice
from urllib.parse import urljoin

import scrapy

data = {
    'keywords': [
        'python',
        'django-rest-framework',
        'jwt',
    ],
    'proxies': [
        '85.238.104.235:47408',
        '213.109.234.4:8080',
    ],
    'type': [
        'Repositories',
        'Issues',
        'Wikis',
    ]
}
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'


class GithubSpider(scrapy.Spider):
    name = 'github_crawler'
    base_url = 'https://github.com/'
    custom_settings = {
        'DOWNLOAD_TIMEOUT': 30,
    }

    def start_requests(self):
        for url_part in data['keywords']:
            yield scrapy.Request(
                url='https://github.com/search?q={}'.format(url_part),
                headers={'user-agent': USER_AGENT},
                callback=self.parse,
                errback=self.retry_error_request,
                dont_filter=True,
                meta={
                    'proxy': 'http://{}'.format(choice(data['proxies'])),
                    'type': url_part,
                    'dont_merge_cookies': True,
                },
            )

    def parse(self, response):
        key = response.meta['type']
        repos_data = {key: {
            'Repositories': [],
            'Issues': [],
            'Wikis': [],
        }}
        for cat in response.css('.repo-list a[data-hydro-click]'):
            url = urljoin(self.base_url, cat.css('::attr(href)').extract_first())
            yield scrapy.Request(
                url,
                headers={'user-agent': USER_AGENT},
                dont_filter=True,
                callback=self.parse_extra,
                meta={
                    'key': key,
                    'repos_data': repos_data,
                    'prev_resp': response,
                    'dont_merge_cookies': True,
                },
            )

    def parse_extra(self, response):
        key = response.meta['key']
        repos_data = response.meta['repos_data']
        language_stats = {}
        for lang in response.css('.repository-lang-stats-graph > span'):
            name = lang.css('::attr(aria-label)').extract_first().split()
            language_stats[name[0]] = name[1]
        repos_data[key]['Repositories'].append({
            'url': response.url,
            'extra': {
                'owner': response.css('[rel=author]::text').extract_first().strip(),
                'language_stats': language_stats,
            }
        })
        for cat in response.meta['prev_resp'].css('.menu.border > a'):
            name = cat.css('::text').extract_first().strip()
            if name not in data['type'] or name == 'Repositories':
                continue

            url = urljoin(self.base_url, cat.css('::attr(href)').extract_first())
            yield scrapy.Request(
                url,
                headers={'user-agent': USER_AGENT},
                callback=self.get_issue_wiki,
                meta={
                    'repos_data': repos_data,
                    'key': key,
                },
            )

    def get_issue_wiki(self, response):
        repos_data = response.meta['repos_data']
        key = response.meta['key']
        sel_cat = response.css('.menu-item.selected::text').extract_first()
        for cat in response.css('.issue-list a[data-hydro-click], #wiki_search_results a[data-hydro-click]'):
            url = urljoin(self.base_url, cat.css('::attr(href)').extract_first())
            repos_data[key][sel_cat].append({'url': url})
        if all(repos_data[key].values()):
            yield repos_data

    def retry_error_request(self, response):
        url = response.request.url
        category = response.request.meta.get('category')
        retry = response.request.meta.get('retry', 1)
        if retry < 5:
            yield scrapy.Request(
                url,
                headers={'user-agent': USER_AGENT},
                callback=response.request.callback,
                errback=self.retry_error_request,
                dont_filter=True,
                meta={
                    'category': category,
                    'retry': retry + 1,
                }
            )
