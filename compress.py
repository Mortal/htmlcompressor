import io
import sys
import html5lib
from xml.etree.ElementTree import ElementTree


def element_to_html(element):
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


def tree_equal(t1, t2):
    return (t1.tag == t2.tag and
            t1.text == t2.text and
            len(t1) == len(t2) and
            all(c1.tail == c2.tail for c1, c2 in zip(t1, t2)) and
            all(tree_equal(c1, c2) for c1, c2 in zip(t1, t2)))


def main():
    input = sys.stdin.read()
    document = html5lib.parse(input)
    input2 = element_to_html(document)
    print("Input size: %s bytes" % len(input))
    print("Input size 2: %s bytes" % len(input2))
    input3 = input2.replace('<html>', '')
    document3 = html5lib.parse(input3)
    print("Input 3: %s bytes" % len(input3))
    print(tree_equal(document, document3))
    input4 = input3.replace('<head>', '')
    document4 = html5lib.parse(input4)
    print("Input 4: %s bytes" % len(input4))
    print(tree_equal(document3, document4))


if __name__ == "__main__":
    main()
