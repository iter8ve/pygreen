from smartypants import smartypants
from markdown import markdown
import re


def smartydown(val):
    return smartypants(markdown(val))

def sectionize(val):
    hr_patt = re.compile('<hr \/>')
    content = smartydown(val)
    repl = r'</article>\n<article class="column">'
    if hr_patt.search(content):
        classname = "two-column"
        content = hr_patt.sub(repl, content)
    else:
        classname = "one-column"
    rv = '\n'.join((
        '<section class="{0}">'.format(classname),
        '<article class="column">',
        content,
        '</article>',
        '</section>'
    ))
    print rv
    return rv
