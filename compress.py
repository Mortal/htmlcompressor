import io
import re
import sys
import time
import html5lib
import functools
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def element_tag_in_list(list, element):
    p = '{%s}' % NS['h']
    if element.tag.startswith(p):
        return element.tag[len(p):] in list


# No ending tag
void_elements = (
    '''area base br col command embed hr img input keygen link meta param
    source track wbr'''.split())
is_void_element = functools.partial(element_tag_in_list, void_elements)

# Don't strip whitespace inside these
pre_elements = 'xmp pre plaintext'.split()
is_pre_element = functools.partial(element_tag_in_list, pre_elements)

# Don't strip whitespace inside these, and don't escape &, <, >
script_elements = 'script style'.split()
is_script_element = functools.partial(element_tag_in_list, script_elements)

# Strip whitespace after these start and end tags
block_elements = (
    '''address article aside blockquote blockquote body center dd details dir
    div dl dt figcaption figure footer form frameset h1 h2 h3 h4 h5 h6 header
    hgroup hr html listing main menu multicol nav ol p plaintext pre section
    summary ul xmp'''.split())  # From Firefox html.css
block_elements.append('head')  # Also strip after <head> and after </head>
is_block_element = functools.partial(element_tag_in_list, block_elements)


def serialize_html(write, elem, **kwargs):
    tag = elem.tag
    text = elem.text
    if tag is ET.Comment:
        write("<!--%s-->" % text)
    elif tag is ET.ProcessingInstruction:
        write("<?%s?>" % text)
    else:
        if tag.startswith('{'):
            uri, tag = tag[1:].rsplit("}", 1)
        if tag is None:
            if text:
                write(ET._escape_cdata(text))
            for e in elem:
                serialize_html(write, e)
        else:
            write("<" + tag)
            items = list(elem.items())
            if items:
                for k, v in sorted(items):  # lexical order
                    if isinstance(k, ET.QName):
                        k = k.text
                    if isinstance(v, ET.QName):
                        v = v.text
                    else:
                        v = ET._escape_attrib(v)
                    if not v or any(c in v for c in ' ='):
                        v = '"%s"' % v
                    write(" %s=%s" % (k, v))
            if text or len(elem) or not is_void_element(elem):
                write(">")
                if text:
                    write(text if tag in ('script', 'style')
                          else ET._escape_cdata(text))
                for e in elem:
                    serialize_html(write, e)
                write("</" + tag + ">")
            else:
                write(">")
    if elem.tail:
        write(ET._escape_cdata(elem.tail))


def element_to_html_old(element):
    with io.BytesIO() as buf:
        # We cannot use default_namespace,
        # since it incorrectly errors on unnamespaced attributes
        # See: https://bugs.python.org/issue17088
        ElementTree(element).write(
            buf, encoding='utf8', xml_declaration=False,
            method='xml')
        body = buf.getvalue().decode('utf8')

    # Workaround to make it prettier
    body = body.replace(
        ' xmlns:html="http://www.w3.org/1999/xhtml"', '')
    body = body.replace('<html:', '<')
    body = body.replace('</html:', '</')
    return body


def element_to_html(element):
    with io.StringIO() as buf:
        serialize_html(buf.write, element)
        return "<!DOCTYPE html>" + buf.getvalue()


def tree_equal(t1, t2, do_log=True):
    def log(b, s):
        if not b:
            print(s)
        return b

    if do_log:
        def log_eq(a, b, s):
            return log(a == b, (s, a, b))
    else:
        def log_eq(a, b, _):
            return a == b

    return (log_eq(t1.tag, t2.tag, 'tag') and
            log_eq(t1.text or '', t2.text or '', 'text') and
            log_eq(len(t1), len(t2), t1.tag + ' len') and
            log_eq(sorted(t1.keys()), sorted(t2.keys()), t1.tag + ' keys') and
            all(log_eq(t1.get(k), t2.get(k), t1.tag + ' value of ' + k)
                for k in t1.keys()) and
            all(log_eq(c1.tail or '', c2.tail or '', t1.tag + ' tail')
                for c1, c2 in zip(t1, t2)) and
            all(tree_equal(c1, c2) for c1, c2 in zip(t1, t2)))


def default_ws_keep(element):
    return is_pre_element(element) or is_script_element(element)


def strip_insignificant_whitespace(element, keep=default_ws_keep):

    def recurse(element, space_before):
        if keep(element):
            return False

        def collapse(text, before):
            if not text:
                return '', before
            start_space = text.lstrip() != text
            if start_space and not before:
                s = ' '
            else:
                s = ''
            text = re.sub(r'(\S\s)\s+', r'\1', text)
            return s + text.lstrip(), text.rstrip() != text

        element.text, space_before = collapse(
            element.text, space_before or is_block_element(element))
        for child in element:
            space_before = recurse(
                child, space_before=space_before)
            child.tail, space_before = collapse(
                child.tail, space_before or is_block_element(child))

        if is_block_element(element):
            element.text = element.text.lstrip()
            if len(element) > 0:
                element[-1].tail = element[-1].tail.rstrip()
            space_before = True

        return space_before

    recurse(element, space_before=False)
    if is_block_element(element) and element.tail:
        element.tail = element.tail.lstrip()


def main():
    t1 = time.time()
    input = sys.stdin.read()
    print("Input size: %s bytes" % len(input))
    document = html5lib.parse(input)
    input2 = element_to_html(document)
    document2 = html5lib.parse(input2)
    print("Roundtrip element_to_html: %s bytes" % len(input2))
    assert tree_equal(document, document2)
    document3 = html5lib.parse(input2)
    strip_insignificant_whitespace(document3)
    input3 = element_to_html(document3)
    print("Strip insignificant whitespace: %s bytes" % len(input3))
    if not tree_equal(document2, document3):
        print("Stripping insignificant whitespace changes parsing, " +
              "but we ignore that")
    document3b = html5lib.parse(input3)
    assert tree_equal(document3, document3b)

    def sound(x):
        document = html5lib.parse(x)
        return tree_equal(document3, document)

    pattern = (r'<(html|head|body|colgroup|tbody)>|' +
               r'</(head|body|html|p|li|dt|dd|rt|rp|optgroup|option|' +
               r'menuitem|colgroup|caption|thead|tbody|tfoot|tr|td|th)>')

    texts = []
    matches = []
    positions = []
    i = 0
    for mo in re.finditer(pattern, input3):
        texts.append(input3[i:mo.start()])
        matches.append(input3[mo.start():mo.end()])
        positions.append(mo.start())
        i = mo.end()
    tail = input3[i:]
    assert ''.join(a+b for a, b in zip(texts, matches)) + tail == input3

    decision = []

    def pick_one(m):
        # print("Pick one among %s" % ' '.join(m))
        if m and m[0] == '<tbody>':
            return 1

        try:
            return next(i+1 for i in range(len(m)-1)
                        if m[i] == '</thead>' and m[i+1] == '<tbody>')
        except StopIteration:
            pass

    while len(decision) < len(matches):
        lo = len(decision)
        hi = len(matches) + 1

        # Monotone predicate: Given i in [len(decision), len(matches)],
        # is it ok to exclude the first i?

        def test(mid):
            # Try forming a text where all in [len(decision), mid) are excluded
            x = ''.join(texts[len(decision):mid])
            y = ''.join(a + b for a, b in zip(texts[mid:], matches[mid:]))
            z = prefix + x + y + tail
            return sound(z)

        # Binary search problem:
        # Find the first i in [lo, len(matches)+1)
        # where the predicate is false.
        prefix = ''.join(a + (b if c else '')
                         for a, b, c in zip(texts, matches, decision))

        # Can pick_one help us find the bad tag?
        guide = pick_one(matches[lo:hi-1])
        if guide is not None:
            if test(lo + guide):
                lo = lo + guide
                if lo + 1 < hi and not test(lo + 1):
                    hi = lo + 1
        # Otherwise, can we exclude everything?
        elif test(hi - 1):
            lo = hi - 1
        # Otherwise, actually do the binary search.
        while lo + 1 < hi:
            mid = lo + pick_one(matches[lo:hi-1])
            # Is excluding decision + [lo, mid) ok?
            print("[%s, %s): Try %s %s" % (lo, hi, mid, ' '.join(matches[len(decision):mid])))
            if test(mid):
                lo = mid
                break
            else:
                hi = mid
        # All up to lo can be safely excluded
        assert len(decision) < lo or lo < len(matches)
        if len(decision) < lo:
            print("Exclude [%s, %s)" % (len(decision), lo))
            decision.extend(False for _ in range(len(decision), lo))
        if lo < len(matches) and lo + 1 == hi:
            print("Include %s: %s in position %s" % (lo, matches[lo], positions[lo]))
            decision.append(True)

    result = ''.join(a + (b if c else '')
                     for a, b, c in zip(texts, matches, decision)) + tail
    with open("output.html", "w") as fp:
        fp.write(result)
    print("output.html: %s bytes" % len(result))
    t2 = time.time()
    print("Took %.2f seconds" % (t2 - t1))


if __name__ == "__main__":
    main()
