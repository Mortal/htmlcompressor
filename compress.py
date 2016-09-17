import io
import re
import sys
import html5lib
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def is_void_element(element):
    return any(element.tag == '{%s}%s' % (NS['h'], t)
               for t in
               '''area base br col command embed hr img input keygen link meta
               param source track wbr'''.split())


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
                    write(" %s=\"%s\"" % (k, v))
            if text or len(elem) or not is_void_element(elem):
                write(">")
                if text:
                    write(text if tag in ('script', 'style') else ET._escape_cdata(text))
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


def tree_equal(t1, t2):
    def log(b, s):
        if not b:
            print(s)
        return b

    def log_eq(a, b, s):
        return log(a == b, (s, a, b))

    return (log_eq(t1.tag, t2.tag, 'tag') and
            log_eq(t1.text or '', t2.text or '', 'text') and
            log_eq(len(t1), len(t2), 'len') and
            all(log_eq(c1.tail or '', c2.tail or '', t1.tag + ' tail') for c1, c2 in zip(t1, t2)) and
            all(tree_equal(c1, c2) for c1, c2 in zip(t1, t2)))


def whitespace_model_pre(element):
    if any(element.tag == '{%s}%s' % (NS['h'], t)
           for t in 'xmp pre plaintext style script'.split()):
        return True


def strip_insignificant_whitespace(element, keep=whitespace_model_pre,
                                   space_before=False):
    if keep(element):
        return False

    main_element = any(element.tag == '{%s}%s' % (NS['h'], t)
                       for t in 'html head body'.split())

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

    element.text, space_before = collapse(element.text, space_before)
    for child in element:
        space_before = strip_insignificant_whitespace(
            child, keep=keep, space_before=space_before)
        child.tail, space_before = collapse(child.tail, space_before)

    if main_element:
        element.text = element.text.lstrip()
        if len(element) > 0:
            element[-1].tail = element[-1].tail.rstrip()

    return space_before


def main():
    input = sys.stdin.read()
    print("Input size: %s bytes" % len(input))
    # print(input)
    document = html5lib.parse(input)
    input2 = element_to_html(document)
    document2 = html5lib.parse(input2)
    print("Roundtrip element_to_html: %s bytes" % len(input2))
    print(tree_equal(document, document2))
    # print(input2)
    document3 = html5lib.parse(input2)
    strip_insignificant_whitespace(document3)
    input3 = element_to_html(document3)
    print("Strip insignificant whitespace: %s bytes" % len(input3))
    print(tree_equal(document2, document3))
    document3b = html5lib.parse(input3)
    print(tree_equal(document3, document3b))
    # print(input3)

    pattern = (r'<(html|head|body|colgroup|tbody)>|' +
               r'</(head|body|html|p|li|dt|dd|rt|rp|optgroup|option|menuitem|' +
               r'colgroup|caption|thead|tbody|tfoot|tr|td|th)>')
    a, b = '', input3

    def count(p, s):
        return sum(1 for mo in re.finditer(p, s))

    while True:
        not_deleted = [a]
        i = 0
        match_start = []
        match_end = []
        for mo in re.finditer(pattern, b):
            j = mo.start()
            match_start.append(j)
            not_deleted.append(b[i:j])
            i = mo.end()
            match_end.append(i)
        if not match_start:
            break
        print(re.search(pattern, b).group(0))
        not_deleted.append(b[i:])
        skip = 0
        while True:
            print("Try skip %s/%s" % (skip, len(match_start)))
            if skip >= len(match_start):
                skip = len(match_start)
                break
            x = not_deleted[:-skip] if skip else not_deleted
            input = ''.join(x) + (b[match_start[-skip]:] if skip else '')
            print(input[:500])
            document = html5lib.parse(input)
            if tree_equal(document3b, document):
                break
            skip = 2*skip if skip else 1
        if not skip:
            break
        a, b = ''.join(not_deleted[:-skip]) + b[match_start[-skip]:match_end[-skip]], b[match_end[-skip]:]
        print("Remove %s tags: %s bytes" % (len(match_start) - skip, len(a)+len(b)))
    input4 = a + b
    # print(input4)


if __name__ == "__main__":
    main()
