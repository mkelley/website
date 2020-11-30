# Licensed under a MIT style license - see LICENSE
import os


class Website:
    """Website generator.

    Processes source files in YAML format with Jinja2 templates.
    Performs special handling for blogs.

    Parameters
    ----------
    target : string
      Output directory.
    templates : string
      Directory with Jinja2 templates.
    source : string
      Directory with source files.
    blogs : list of dict
      A dictionary for each blog configuration, see below.
    valid_files : list of string
      File extensions, including '.', that should be considered as
      inputs in the source directory, e.g., '.html', '.png', etc.
      '.yaml' will always be considered.

    Blog configuration
    ------------------
    path : string
      Location of the blog within website/source directory.
    title : string
      Blog title.
    templates : dict
      navigation : string
        Template to use for blog navigation sections.
      article-list : string
        Template to use for article indices.
    data: dict
      Additional parameters to pass to blog templates.

    """

    def __init__(self, target, templates, source, blogs, valid_files):
        self.target = os.path.normpath(target)
        self.templates = os.path.normpath(templates)
        self.source = os.path.normpath(source)
        self.blogs = blogs
        self.valid_files = list(valid_files) + ['.yaml']

        self.setup_templating()
        self.setup_files()
        self.setup_target()

    def blog_navigation(self, blog, entries):
        """Generates blog navigation section for inclusion in blog entries.

        blog : dict
          The blog's configuration.
        entries : list of dict
          All blog entries.

        """
        from itertools import chain

        if 'navigation' not in blog['templates']:
            return ''

        tags = set(chain.from_iterable([entry.get('tags', [])
                                        for entry in entries]))
        tags = sorted(list(tags), key=lambda s: s.lower())

        year_months = list(set([str(entry['date'])[:7] for entry in entries]))
        year_months.sort(reverse=True)

        dates_by_year = {}
        for ym in year_months:
            year, month = ym.split('-')
            if year not in dates_by_year:
                dates_by_year[year] = []
            dates_by_year[year].append({
                'filename': ym + '.html',
                'name': num2mon[int(month)]
            })

        # do not use self.render because we do not want to save it
        tpf = blog['templates']['navigation']
        template = self.env.get_template(tpf)
        return template.render(tags=tags, dates=dates_by_year, entries=entries,
                               **blog.get('data', {}))

    def date_pages(self, blog, entries, **opts):
        """Generate lists of articles for each blog year-month.

        blog : dict
          The blog's configuration.
        entries : list of dict
          All blog entries.
        **opts : string
          Additional blog data, including 'blog_nav'.

        """

        # organize articles by year-month
        dates = {}
        for i, entry in enumerate(entries):
            date = str(entry['date'])[:7]
            if date not in dates:
                dates[date] = []
            dates[date].append(i)

        index = {
            'template': blog['templates']['article-list'],
            'page_title': blog['title'],
        }
        index.update(opts)
        for date, i in dates.items():
            index.update({
                'entries': [entries[j] for j in i],
                'filename': os.path.join(blog['path'], 'dates', date + '.html'),
                'page_subtitle': date,
            })
            self.render(index)

    def generate(self):
        """Generate the website."""
        self.generate_pages()
        for blog in self.blogs:
            self.generate_blog(blog)

    def generate_blog(self, blog):
        """Generate blog."""

        import shutil

        print('Loading {title} from {path}'.format(**blog))

        entries, drafts, others = self.read_blog(
            blog['path'], blog['article-path'])

        opts = {}
        opts['blog_nav'] = self.blog_navigation(blog, entries)
        opts.update(blog.get('data', {}))

        # article index
        index = {
            'page_title': blog['title'],
            'page_subtitle': 'All',
            'template': blog['templates']['article-list'],
            'filename': os.path.join(
                blog['path'], blog['article-path'], 'index.html'),
        }
        self.render(index, entries=entries, **opts)

        # tag and date pages
        self.tag_pages(blog, entries, **opts)
        self.date_pages(blog, entries, **opts)

        # other pages
        for other in others:
            if isinstance(other, tuple):
                src, tgt = other
                print('  W', tgt)
                shutil.copy(src, tgt)
            else:
                self.render(other, **opts)

        # blog entries
        opts['page_title'] = blog['title']
        for i, entry in enumerate(entries):
            opts['page_subtitle'] = entry['title']
            if i == 0:
                opts['prev'] = ''
            else:
                opts['prev'] = basename(entries[i - 1]['filename'])

            if i + 1 == len(entries):
                opts['next'] = ''
            else:
                opts['next'] = basename(entries[i + 1]['filename'])

            root_path = self.relpath(entry['filename'])
            self.render(entry, **opts)

        # regenerate recent entry with base_url and save to blog
        # index, but keep 'filename' the same.
        recent = entry.copy()
        opts['base_url'] = '<base href={}>'.format(os.path.join(
            blog['article-path'], os.path.basename(entry['filename'])))
        html = self.render(recent, save=False, **opts)

        fn = os.path.join(self.target, blog['path'], 'index.html')
        print('  W', fn)
        with open(fn, 'w') as outf:
            outf.write(html)

    def generate_pages(self):
        """Generate all non-blog pages."""

        import shutil

        print('Writing non-blog pages.')

        files = self.files
        for blog in self.blogs:
            files = files.files_not_in(blog['path'])

        for src, tgt in files.items():
            if src.endswith('yaml'):
                page_data = self.read_yaml(src, tgt)
                self.render(page_data)
            else:
                print('  W', tgt)
                shutil.copy(src, tgt)

    def read_blog(self, path, article_path):
        """Read in blog entries into lists.

        Parameters
        ----------
        path : string
          Website's path to blog.
        article_path
          Name of article directory.

        Returns
        -------
        entries : list of dict
          List of all blog entries.
        drafts : list of dict
          List of all blog entry drafts.
        others : list of dict
          List of all other files found in the blog directory.

        """

        entries = []
        drafts = []
        others = []

        blog_files = self.files.files_in(path)
        articles = self.files.files_in(os.path.join(path, article_path))

        for src, tgt in blog_files.items():
            if not src.endswith('.yaml'):
                others.append((src, tgt))
                continue

            data = self.read_yaml(src, tgt)
            print('  L', data.get('title', data.get('page_title')))
            if src in articles.source_files:
                if 'draft' in data:
                    drafts.append(data)
                else:
                    entries.append(data)
            else:
                others.append(data)

        entries.sort(key=lambda e: e['date'])
        return entries, drafts, others

    def read_yaml(self, src, tgt=None):
        """Read YAML formatted file.

        Parameters
        ----------
        src : string
          Source file name.
        tgt : string, optional
          Output file name, which will be stored as the key
          'filename'.  If `None`, then the output filename will be
          based on `src`

        Returns
        -------
        page_data : dict
          The page data.

        """
        import yaml
        with open(src) as inf:
            page_data = yaml.load(inf)

        if tgt is None:
            tgt = os.path.normpath(src)[len(self.source) + 1:]

        page_data['filename'] = tgt
        if page_data['filename'].startswith(self.target):
            page_data['filename'] = page_data['filename'][len(
                self.target) + 1:]

        return page_data

    def relpath(self, f, base=None):
        """Relative path within website.

        Parameters
        ----------
        f : string
          File name to consider.
        base : string, optional
          Find path to this location.  If `None`, return path to
          website root.

        """
        if base is None:
            base = self.target
        return os.path.relpath(base, os.path.dirname(f))

    def render(self, page_data, save=True, **kwargs):
        """Render page data and save to file.

        Two keys are required:
          'filename' : Output file name.
          'template' : Name of the file template to use.

        Parameters
        ----------
        page_data : dict
          The page data.
        save : bool
          `True` to save the file, `False` to return it as a string.

        """
        from jinja2.exceptions import TemplateNotFound
        tgt = os.path.join(self.target, page_data['filename'])
        template = self.env.get_template(page_data['template'])
        parameters = dict(**kwargs)
        parameters['root_path'] = parameters.get(
            'root_path', self.relpath(tgt))
        html = template.render(page_data, **parameters)
        if save:
            print('  W', tgt)
            with open(tgt, 'w') as outf:
                outf.write(html)
        else:
            return html

    def setup_files(self):
        """Find all needed source files."""
        self.files = FileSet(self.target, self.source)
        for dirpath, dirnames, filenames in os.walk(self.source):
            for f in filenames:
                if os.path.splitext(f)[1] not in self.valid_files:
                    continue
                self.files.append(dirpath, f)

    def setup_templating(self):
        """Setup Jinja2 templates."""
        from jinja2 import Environment, FileSystemLoader
        file_loader = FileSystemLoader(self.templates)
        self.env = Environment(loader=file_loader, trim_blocks=True,
                               lstrip_blocks=True)
        self.env.filters['filequote'] = filequote
        self.env.filters['basename'] = basename
        self.env.filters['dateconv'] = dateconv

    def setup_target(self):
        """Create full target directory tree."""
        print('Checking target directory tree.')
        for d in set([os.path.dirname(f) for f in self.files.target_files]):
            if not os.path.exists(d):
                print('  C', d)
                os.system('mkdir -p {}'.format(d))

        # make blog directories
        for blog in self.blogs:
            for sfx in ['tags', 'dates', blog['article-path']]:
                d = os.path.join(self.target, blog['path'], sfx)
                if not os.path.exists(d):
                    os.system('mkdir -p {}'.format(d))
                    print('  C', d)

    def tag_pages(self, blog, entries, **opts):
        """Generate lists of articles for each blog tag.

        blog : dict
          The blog's configuration.
        entries : list of dict
          All blog entries.
        **opts : string
          Additional blog data, including 'blog_nav'.

        """

        # organize articles by tag
        tags = {}
        for i, entry in enumerate(entries):
            for tag in entry.get('tags', []):
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append(i)

        if len(tags) == 0:
            return

        index = {
            'template': blog['templates']['article-list'],
            'page_title': blog['title'],
        }
        index.update(opts)
        for tag, i in tags.items():
            index.update({
                'entries': [entries[j] for j in i],
                'filename': os.path.join(
                    blog['path'], 'tags', filequote(tag) + '.html'),
                'page_subtitle': tag,
            })
            self.render(index)


class FileSet:
    """Website source and target file pairs.

    yaml source files will be given html target names.

    Parameters
    ----------
    target_path : string
      The target directory.
    source_path : string
      The source directory.

    Attributes
    ----------
    source_files : List of all valid source files.
    target_files : List of all valid source files.

    Methods
    -------
    append : Add a source file.
    files_in : New `FileSet` limited to files in a given directory.
    files_not_in : New `FileSet` without files in a given directory.

    """

    def __init__(self, target_path, source_path):
        self.target_path = os.path.normpath(target_path)
        self.source_path = os.path.normpath(source_path)
        self._files = {}

    def append(self, *args):
        """append(filename) or append(directory, filename)"""
        assert len(args) in [1, 2]
        if len(args) == 1:
            d = os.path.dirname(args[0])
            f = os.path.basename(args[0])
        else:
            d = args[0]
            f = args[1]

        d = os.path.normpath(d)
        assert d.startswith(self.source_path), 'Not in source path: ' + d
        src = os.path.normpath(os.path.join(d, f))
        tgt = os.path.normpath(os.path.join(
            self.target_path, src[len(self.source_path) + 1:]))
        if tgt.endswith('yaml'):
            tgt = tgt[:-4] + 'html'
        self._files[src] = tgt

    def __getitem__(self, k):
        return self._files[k]

    def items(self):
        return self._files.items()

    @property
    def source_files(self):
        return self._files.keys()

    @property
    def target_files(self):
        return self._files.values()

    def files_in(self, d):
        """Files that belong to this directory.

        d : Directory, relative to website root.

        """

        files = FileSet(self.target_path, self.source_path)
        path = os.path.normpath(os.path.join(self.source_path, d))
        for f in self.source_files:
            if f.startswith(path):
                files.append(f)
        return files

    def files_not_in(self, d):
        """Files that do not belong to this directory.

        d : Directory, relative to website root.

        """

        files = FileSet(self.target_path, self.source_path)
        path = os.path.normpath(os.path.join(self.source_path, d))
        for f in self.source_files:
            if not f.startswith(path):
                files.append(f)
        return files


num2mon = {}
for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()):
    num2mon[i + 1] = m
del i, m


def ym2MonYYYY(ym):
    '''2018-08 -> Aug 2018'''
    y, m = ym.split('-')
    return '{} {}'.format(num2mon[int(m)], y)


def filequote(text):
    """Transform text to file name."""
    trans = str.maketrans(' /()', '____')
    return text.translate(trans)


def basename(url):
    from urllib.parse import urlparse
    return os.path.basename(urlparse(url).path)


def dateconv(date, from_format, to_format):
    from datetime import datetime
    if date is None:
        return ''
    return datetime.strptime(date, from_format).strftime(to_format)
