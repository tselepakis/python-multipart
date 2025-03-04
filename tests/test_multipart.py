import os
import sys
import yaml
import random
import tempfile
import unittest
from .compat import (
    parametrize,
    parametrize_class,
    slow_test,
)
from io import BytesIO
from unittest.mock import Mock

from multipart.multipart import *


# Get the current directory for our later test cases.
curr_dir = os.path.abspath(os.path.dirname(__file__))


def force_bytes(val):
    if isinstance(val, str):
        val = val.encode(sys.getfilesystemencoding())

    return val


class TestField(unittest.TestCase):
    def setUp(self):
        self.f = Field('foo')

    def test_name(self):
        self.assertEqual(self.f.field_name, 'foo')

    def test_data(self):
        self.f.write(b'test123')
        self.assertEqual(self.f.value, b'test123')

    def test_cache_expiration(self):
        self.f.write(b'test')
        self.assertEqual(self.f.value, b'test')
        self.f.write(b'123')
        self.assertEqual(self.f.value, b'test123')

    def test_finalize(self):
        self.f.write(b'test123')
        self.f.finalize()
        self.assertEqual(self.f.value, b'test123')

    def test_close(self):
        self.f.write(b'test123')
        self.f.close()
        self.assertEqual(self.f.value, b'test123')

    def test_from_value(self):
        f = Field.from_value(b'name', b'value')
        self.assertEqual(f.field_name, b'name')
        self.assertEqual(f.value, b'value')

        f2 = Field.from_value(b'name', None)
        self.assertEqual(f2.value, None)

    def test_equality(self):
        f1 = Field.from_value(b'name', b'value')
        f2 = Field.from_value(b'name', b'value')

        self.assertEqual(f1, f2)

    def test_equality_with_other(self):
        f = Field.from_value(b'foo', b'bar')
        self.assertFalse(f == b'foo')
        self.assertFalse(b'foo' == f)

    def test_set_none(self):
        f = Field(b'foo')
        self.assertEqual(f.value, b'')

        f.set_none()
        self.assertEqual(f.value, None)


class TestFile(unittest.TestCase):
    def setUp(self):
        self.c = {}
        self.d = force_bytes(tempfile.mkdtemp())
        self.f = File(b'foo.txt', config=self.c)

    def assert_data(self, data):
        f = self.f.file_object
        f.seek(0)
        self.assertEqual(f.read(), data)
        f.seek(0)
        f.truncate()

    def assert_exists(self):
        full_path = os.path.join(self.d, self.f.actual_file_name)
        self.assertTrue(os.path.exists(full_path))

    def test_simple(self):
        self.f.write(b'foobar')
        self.assert_data(b'foobar')

    def test_invalid_write(self):
        m = Mock()
        m.write.return_value = 5
        self.f._fileobj = m
        v = self.f.write(b'foobar')
        self.assertEqual(v, 5)

    def test_file_fallback(self):
        self.c['MAX_MEMORY_FILE_SIZE'] = 1

        self.f.write(b'1')
        self.assertTrue(self.f.in_memory)
        self.assert_data(b'1')

        self.f.write(b'123')
        self.assertFalse(self.f.in_memory)
        self.assert_data(b'123')

        # Test flushing too.
        old_obj = self.f.file_object
        self.f.flush_to_disk()
        self.assertFalse(self.f.in_memory)
        self.assertIs(self.f.file_object, old_obj)

    def test_file_fallback_with_data(self):
        self.c['MAX_MEMORY_FILE_SIZE'] = 10

        self.f.write(b'1' * 10)
        self.assertTrue(self.f.in_memory)

        self.f.write(b'2' * 10)
        self.assertFalse(self.f.in_memory)

        self.assert_data(b'11111111112222222222')

    def test_file_name(self):
        # Write to this dir.
        self.c['UPLOAD_DIR'] = self.d
        self.c['MAX_MEMORY_FILE_SIZE'] = 10

        # Write.
        self.f.write(b'12345678901')
        self.assertFalse(self.f.in_memory)

        # Assert that the file exists
        self.assertIsNotNone(self.f.actual_file_name)
        self.assert_exists()

    def test_file_full_name(self):
        # Write to this dir.
        self.c['UPLOAD_DIR'] = self.d
        self.c['UPLOAD_KEEP_FILENAME'] = True
        self.c['MAX_MEMORY_FILE_SIZE'] = 10

        # Write.
        self.f.write(b'12345678901')
        self.assertFalse(self.f.in_memory)

        # Assert that the file exists
        self.assertEqual(self.f.actual_file_name, b'foo')
        self.assert_exists()

    def test_file_full_name_with_ext(self):
        self.c['UPLOAD_DIR'] = self.d
        self.c['UPLOAD_KEEP_FILENAME'] = True
        self.c['UPLOAD_KEEP_EXTENSIONS'] = True
        self.c['MAX_MEMORY_FILE_SIZE'] = 10

        # Write.
        self.f.write(b'12345678901')
        self.assertFalse(self.f.in_memory)

        # Assert that the file exists
        self.assertEqual(self.f.actual_file_name, b'foo.txt')
        self.assert_exists()

    def test_file_full_name_with_ext(self):
        self.c['UPLOAD_DIR'] = self.d
        self.c['UPLOAD_KEEP_FILENAME'] = True
        self.c['UPLOAD_KEEP_EXTENSIONS'] = True
        self.c['MAX_MEMORY_FILE_SIZE'] = 10

        # Write.
        self.f.write(b'12345678901')
        self.assertFalse(self.f.in_memory)

        # Assert that the file exists
        self.assertEqual(self.f.actual_file_name, b'foo.txt')
        self.assert_exists()

    def test_no_dir_with_extension(self):
        self.c['UPLOAD_KEEP_EXTENSIONS'] = True
        self.c['MAX_MEMORY_FILE_SIZE'] = 10

        # Write.
        self.f.write(b'12345678901')
        self.assertFalse(self.f.in_memory)

        # Assert that the file exists
        ext = os.path.splitext(self.f.actual_file_name)[1]
        self.assertEqual(ext, b'.txt')
        self.assert_exists()

    def test_invalid_dir_with_name(self):
        # Write to this dir.
        self.c['UPLOAD_DIR'] = force_bytes(os.path.join('/', 'tmp', 'notexisting'))
        self.c['UPLOAD_KEEP_FILENAME'] = True
        self.c['MAX_MEMORY_FILE_SIZE'] = 5

        # Write.
        with self.assertRaises(FileError):
            self.f.write(b'1234567890')

    def test_invalid_dir_no_name(self):
        # Write to this dir.
        self.c['UPLOAD_DIR'] = force_bytes(os.path.join('/', 'tmp', 'notexisting'))
        self.c['UPLOAD_KEEP_FILENAME'] = False
        self.c['MAX_MEMORY_FILE_SIZE'] = 5

        # Write.
        with self.assertRaises(FileError):
            self.f.write(b'1234567890')

    # TODO: test uploading two files with the same name.


class TestParseOptionsHeader(unittest.TestCase):
    def test_simple(self):
        t, p = parse_options_header('application/json')
        self.assertEqual(t, b'application/json')
        self.assertEqual(p, {})

    def test_blank(self):
        t, p = parse_options_header('')
        self.assertEqual(t, b'')
        self.assertEqual(p, {})

    def test_single_param(self):
        t, p = parse_options_header('application/json;par=val')
        self.assertEqual(t, b'application/json')
        self.assertEqual(p, {b'par': b'val'})

    def test_single_param_with_spaces(self):
        t, p = parse_options_header(b'application/json;     par=val')
        self.assertEqual(t, b'application/json')
        self.assertEqual(p, {b'par': b'val'})

    def test_multiple_params(self):
        t, p = parse_options_header(b'application/json;par=val;asdf=foo')
        self.assertEqual(t, b'application/json')
        self.assertEqual(p, {b'par': b'val', b'asdf': b'foo'})

    def test_quoted_param(self):
        t, p = parse_options_header(b'application/json;param="quoted"')
        self.assertEqual(t, b'application/json')
        self.assertEqual(p, {b'param': b'quoted'})

    def test_quoted_param_with_semicolon(self):
        t, p = parse_options_header(b'application/json;param="quoted;with;semicolons"')
        self.assertEqual(p[b'param'], b'quoted;with;semicolons')

    def test_quoted_param_with_escapes(self):
        t, p = parse_options_header(b'application/json;param="This \\" is \\" a \\" quote"')
        self.assertEqual(p[b'param'], b'This " is " a " quote')

    def test_handles_ie6_bug(self):
        t, p = parse_options_header(b'text/plain; filename="C:\\this\\is\\a\\path\\file.txt"')

        self.assertEqual(p[b'filename'], b'file.txt')
    
    def test_redos_attack_header(self):
        t, p = parse_options_header(b'application/x-www-form-urlencoded; !="\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\')
        # If vulnerable, this test wouldn't finish, the line above would hang
        self.assertIn(b'"\\', p[b'!'])


class TestBaseParser(unittest.TestCase):
    def setUp(self):
        self.b = BaseParser()
        self.b.callbacks = {}

    def test_callbacks(self):
        # The stupid list-ness is to get around lack of nonlocal on py2
        l = [0]
        def on_foo():
            l[0] += 1

        self.b.set_callback('foo', on_foo)
        self.b.callback('foo')
        self.assertEqual(l[0], 1)

        self.b.set_callback('foo', None)
        self.b.callback('foo')
        self.assertEqual(l[0], 1)


class TestQuerystringParser(unittest.TestCase):
    def assert_fields(self, *args, **kwargs):
        if kwargs.pop('finalize', True):
            self.p.finalize()

        self.assertEqual(self.f, list(args))
        if kwargs.get('reset', True):
            self.f = []

    def setUp(self):
        self.reset()

    def reset(self):
        self.f = []

        name_buffer = []
        data_buffer = []

        def on_field_name(data, start, end):
            name_buffer.append(data[start:end])

        def on_field_data(data, start, end):
            data_buffer.append(data[start:end])

        def on_field_end():
            self.f.append((
                b''.join(name_buffer),
                b''.join(data_buffer)
            ))

            del name_buffer[:]
            del data_buffer[:]

        callbacks = {
            'on_field_name': on_field_name,
            'on_field_data': on_field_data,
            'on_field_end': on_field_end
        }

        self.p = QuerystringParser(callbacks)

    def test_simple_querystring(self):
        self.p.write(b'foo=bar')

        self.assert_fields((b'foo', b'bar'))

    def test_querystring_blank_beginning(self):
        self.p.write(b'&foo=bar')

        self.assert_fields((b'foo', b'bar'))

    def test_querystring_blank_end(self):
        self.p.write(b'foo=bar&')

        self.assert_fields((b'foo', b'bar'))

    def test_multiple_querystring(self):
        self.p.write(b'foo=bar&asdf=baz')

        self.assert_fields(
            (b'foo', b'bar'),
            (b'asdf', b'baz')
        )

    def test_streaming_simple(self):
        self.p.write(b'foo=bar&')
        self.assert_fields(
            (b'foo', b'bar'),
            finalize=False
        )

        self.p.write(b'asdf=baz')
        self.assert_fields(
            (b'asdf', b'baz')
        )

    def test_streaming_break(self):
        self.p.write(b'foo=one')
        self.assert_fields(finalize=False)

        self.p.write(b'two')
        self.assert_fields(finalize=False)

        self.p.write(b'three')
        self.assert_fields(finalize=False)

        self.p.write(b'&asd')
        self.assert_fields(
            (b'foo', b'onetwothree'),
            finalize=False
        )

        self.p.write(b'f=baz')
        self.assert_fields(
            (b'asdf', b'baz')
        )

    def test_semicolon_separator(self):
        self.p.write(b'foo=bar;asdf=baz')

        self.assert_fields(
            (b'foo', b'bar'),
            (b'asdf', b'baz')
        )

    def test_too_large_field(self):
        self.p.max_size = 15

        # Note: len = 8
        self.p.write(b"foo=bar&")
        self.assert_fields((b'foo', b'bar'), finalize=False)

        # Note: len = 8, only 7 bytes processed
        self.p.write(b'a=123456')
        self.assert_fields((b'a', b'12345'))

    def test_invalid_max_size(self):
        with self.assertRaises(ValueError):
            p = QuerystringParser(max_size=-100)

    def test_strict_parsing_pass(self):
        data = b'foo=bar&another=asdf'
        for first, last in split_all(data):
            self.reset()
            self.p.strict_parsing = True

            print(f"{first!r} / {last!r}")

            self.p.write(first)
            self.p.write(last)
            self.assert_fields((b'foo', b'bar'), (b'another', b'asdf'))

    def test_strict_parsing_fail_double_sep(self):
        data = b'foo=bar&&another=asdf'
        for first, last in split_all(data):
            self.reset()
            self.p.strict_parsing = True

            cnt = 0
            with self.assertRaises(QuerystringParseError) as cm:
                cnt += self.p.write(first)
                cnt += self.p.write(last)
                self.p.finalize()

            # The offset should occur at 8 bytes into the data (as a whole),
            # so we calculate the offset into the chunk.
            if cm is not None:
                self.assertEqual(cm.exception.offset, 8 - cnt)

    def test_double_sep(self):
        data = b'foo=bar&&another=asdf'
        for first, last in split_all(data):
            print(f" {first!r} / {last!r} ")
            self.reset()

            cnt = 0
            cnt += self.p.write(first)
            cnt += self.p.write(last)

            self.assert_fields((b'foo', b'bar'), (b'another', b'asdf'))

    def test_strict_parsing_fail_no_value(self):
        self.p.strict_parsing = True
        with self.assertRaises(QuerystringParseError) as cm:
            self.p.write(b'foo=bar&blank&another=asdf')

        if cm is not None:
            self.assertEqual(cm.exception.offset, 8)

    def test_success_no_value(self):
        self.p.write(b'foo=bar&blank&another=asdf')
        self.assert_fields(
            (b'foo', b'bar'),
            (b'blank', b''),
            (b'another', b'asdf')
        )

    def test_repr(self):
        # Issue #29; verify we don't assert on repr()
        _ignored = repr(self.p)


class TestOctetStreamParser(unittest.TestCase):
    def setUp(self):
        self.d = []
        self.started = 0
        self.finished = 0

        def on_start():
            self.started += 1

        def on_data(data, start, end):
            self.d.append(data[start:end])

        def on_end():
            self.finished += 1

        callbacks = {
            'on_start': on_start,
            'on_data': on_data,
            'on_end': on_end
        }

        self.p = OctetStreamParser(callbacks)

    def assert_data(self, data, finalize=True):
        self.assertEqual(b''.join(self.d), data)
        self.d = []

    def assert_started(self, val=True):
        if val:
            self.assertEqual(self.started, 1)
        else:
            self.assertEqual(self.started, 0)

    def assert_finished(self, val=True):
        if val:
            self.assertEqual(self.finished, 1)
        else:
            self.assertEqual(self.finished, 0)

    def test_simple(self):
        # Assert is not started
        self.assert_started(False)

        # Write something, it should then be started + have data
        self.p.write(b'foobar')
        self.assert_started()
        self.assert_data(b'foobar')

        # Finalize, and check
        self.assert_finished(False)
        self.p.finalize()
        self.assert_finished()

    def test_multiple_chunks(self):
        self.p.write(b'foo')
        self.p.write(b'bar')
        self.p.write(b'baz')
        self.p.finalize()

        self.assert_data(b'foobarbaz')
        self.assert_finished()

    def test_max_size(self):
        self.p.max_size = 5

        self.p.write(b'0123456789')
        self.p.finalize()

        self.assert_data(b'01234')
        self.assert_finished()

    def test_invalid_max_size(self):
        with self.assertRaises(ValueError):
            q = OctetStreamParser(max_size='foo')


class TestBase64Decoder(unittest.TestCase):
    # Note: base64('foobar') == 'Zm9vYmFy'
    def setUp(self):
        self.f = BytesIO()
        self.d = Base64Decoder(self.f)

    def assert_data(self, data, finalize=True):
        if finalize:
            self.d.finalize()

        self.f.seek(0)
        self.assertEqual(self.f.read(), data)
        self.f.seek(0)
        self.f.truncate()

    def test_simple(self):
        self.d.write(b'Zm9vYmFy')
        self.assert_data(b'foobar')

    def test_bad(self):
        with self.assertRaises(DecodeError):
            self.d.write(b'Zm9v!mFy')

    def test_split_properly(self):
        self.d.write(b'Zm9v')
        self.d.write(b'YmFy')
        self.assert_data(b'foobar')

    def test_bad_split(self):
        buff = b'Zm9v'
        for i in range(1, 4):
            first, second = buff[:i], buff[i:]

            self.setUp()
            self.d.write(first)
            self.d.write(second)
            self.assert_data(b'foo')

    def test_long_bad_split(self):
        buff = b'Zm9vYmFy'
        for i in range(5, 8):
            first, second = buff[:i], buff[i:]

            self.setUp()
            self.d.write(first)
            self.d.write(second)
            self.assert_data(b'foobar')

    def test_close_and_finalize(self):
        parser = Mock()
        f = Base64Decoder(parser)

        f.finalize()
        parser.finalize.assert_called_once_with()

        f.close()
        parser.close.assert_called_once_with()

    def test_bad_length(self):
        self.d.write(b'Zm9vYmF')        # missing ending 'y'

        with self.assertRaises(DecodeError):
            self.d.finalize()


class TestQuotedPrintableDecoder(unittest.TestCase):
    def setUp(self):
        self.f = BytesIO()
        self.d = QuotedPrintableDecoder(self.f)

    def assert_data(self, data, finalize=True):
        if finalize:
            self.d.finalize()

        self.f.seek(0)
        self.assertEqual(self.f.read(), data)
        self.f.seek(0)
        self.f.truncate()

    def test_simple(self):
        self.d.write(b'foobar')
        self.assert_data(b'foobar')

    def test_with_escape(self):
        self.d.write(b'foo=3Dbar')
        self.assert_data(b'foo=bar')

    def test_with_newline_escape(self):
        self.d.write(b'foo=\r\nbar')
        self.assert_data(b'foobar')

    def test_with_only_newline_escape(self):
        self.d.write(b'foo=\nbar')
        self.assert_data(b'foobar')

    def test_with_split_escape(self):
        self.d.write(b'foo=3')
        self.d.write(b'Dbar')
        self.assert_data(b'foo=bar')

    def test_with_split_newline_escape_1(self):
        self.d.write(b'foo=\r')
        self.d.write(b'\nbar')
        self.assert_data(b'foobar')

    def test_with_split_newline_escape_2(self):
        self.d.write(b'foo=')
        self.d.write(b'\r\nbar')
        self.assert_data(b'foobar')

    def test_close_and_finalize(self):
        parser = Mock()
        f = QuotedPrintableDecoder(parser)

        f.finalize()
        parser.finalize.assert_called_once_with()

        f.close()
        parser.close.assert_called_once_with()

    def test_not_aligned(self):
        """
        https://github.com/andrew-d/python-multipart/issues/6
        """
        self.d.write(b'=3AX')
        self.assert_data(b':X')

        # Additional offset tests
        self.d.write(b'=3')
        self.d.write(b'AX')
        self.assert_data(b':X')

        self.d.write(b'q=3AX')
        self.assert_data(b'q:X')


# Load our list of HTTP test cases.
http_tests_dir = os.path.join(curr_dir, 'test_data', 'http')

# Read in all test cases and load them.
NON_PARAMETRIZED_TESTS = {'single_field_blocks'}
http_tests = []
for f in os.listdir(http_tests_dir):
    # Only load the HTTP test cases.
    fname, ext = os.path.splitext(f)
    if fname in NON_PARAMETRIZED_TESTS:
        continue

    if ext == '.http':
        # Get the YAML file and load it too.
        yaml_file = os.path.join(http_tests_dir, fname + '.yaml')

        # Load both.
        with open(os.path.join(http_tests_dir, f), 'rb') as f:
            test_data = f.read()

        with open(yaml_file, 'rb') as f:
            yaml_data = yaml.safe_load(f)

        http_tests.append({
            'name': fname,
            'test': test_data,
            'result': yaml_data
        })


def split_all(val):
    """
    This function will split an array all possible ways.  For example:
        split_all([1,2,3,4])
    will give:
        ([1], [2,3,4]), ([1,2], [3,4]), ([1,2,3], [4])
    """
    for i in range(1, len(val) - 1):
        yield (val[:i], val[i:])


@parametrize_class
class TestFormParser(unittest.TestCase):
    def make(self, boundary, config={}):
        self.ended = False
        self.files = []
        self.fields = []

        def on_field(f):
            self.fields.append(f)

        def on_file(f):
            self.files.append(f)

        def on_end():
            self.ended = True

        # Get a form-parser instance.
        self.f = FormParser('multipart/form-data', on_field, on_file, on_end,
                            boundary=boundary, config=config)

    def assert_file_data(self, f, data):
        o = f.file_object
        o.seek(0)
        file_data = o.read()
        self.assertEqual(file_data, data)

    def assert_file(self, field_name, file_name, data):
        # Find this file.
        found = None
        for f in self.files:
            if f.field_name == field_name:
                found = f
                break

        # Assert that we found it.
        self.assertIsNotNone(found)

        try:
            # Assert about this file.
            self.assert_file_data(found, data)
            self.assertEqual(found.file_name, file_name)

            # Remove it from our list.
            self.files.remove(found)
        finally:
            # Close our file
            found.close()

    def assert_field(self, name, value):
        # Find this field in our fields list.
        found = None
        for f in self.fields:
            if f.field_name == name:
                found = f
                break

        # Assert that it exists and matches.
        self.assertIsNotNone(found)
        self.assertEqual(value, found.value)

        # Remove it for future iterations.
        self.fields.remove(found)

    @parametrize('param', http_tests)
    def test_http(self, param):
        # Firstly, create our parser with the given boundary.
        boundary = param['result']['boundary']
        if isinstance(boundary, str):
            boundary = boundary.encode('latin-1')
        self.make(boundary)

        # Now, we feed the parser with data.
        exc = None
        try:
            processed = self.f.write(param['test'])
            self.f.finalize()
        except MultipartParseError as e:
            processed = 0
            exc = e

        # print(repr(param))
        # print("")
        # print(repr(self.fields))
        # print(repr(self.files))

        # Do we expect an error?
        if 'error' in param['result']['expected']:
            self.assertIsNotNone(exc)
            self.assertEqual(param['result']['expected']['error'], exc.offset)
            return

        # No error!
        self.assertEqual(processed, len(param['test']))

        # Assert that the parser gave us the appropriate fields/files.
        for e in param['result']['expected']:
            # Get our type and name.
            type = e['type']
            name = e['name'].encode('latin-1')

            if type == 'field':
                self.assert_field(name, e['data'])

            elif type == 'file':
                self.assert_file(
                    name,
                    e['file_name'].encode('latin-1'),
                    e['data']
                )

            else:
                assert False

    def test_random_splitting(self):
        """
        This test runs a simple multipart body with one field and one file
        through every possible split.
        """
        # Load test data.
        test_file = 'single_field_single_file.http'
        with open(os.path.join(http_tests_dir, test_file), 'rb') as f:
            test_data = f.read()

        # We split the file through all cases.
        for first, last in split_all(test_data):
            # Create form parser.
            self.make('boundary')

            # Feed with data in 2 chunks.
            i = 0
            i += self.f.write(first)
            i += self.f.write(last)
            self.f.finalize()

            # Assert we processed everything.
            self.assertEqual(i, len(test_data))

            # Assert that our file and field are here.
            self.assert_field(b'field', b'test1')
            self.assert_file(b'file', b'file.txt', b'test2')

    def test_feed_single_bytes(self):
        """
        This test parses a simple multipart body 1 byte at a time.
        """
        # Load test data.
        test_file = 'single_field_single_file.http'
        with open(os.path.join(http_tests_dir, test_file), 'rb') as f:
            test_data = f.read()

        # Create form parser.
        self.make('boundary')

        # Write all bytes.
        # NOTE: Can't simply do `for b in test_data`, since that gives
        # an integer when iterating over a bytes object on Python 3.
        i = 0
        for x in range(len(test_data)):
            b = test_data[x:x + 1]
            i += self.f.write(b)

        self.f.finalize()

        # Assert we processed everything.
        self.assertEqual(i, len(test_data))

        # Assert that our file and field are here.
        self.assert_field(b'field', b'test1')
        self.assert_file(b'file', b'file.txt', b'test2')

    def test_feed_blocks(self):
        """
        This test parses a simple multipart body 1 byte at a time.
        """
        # Load test data.
        test_file = 'single_field_blocks.http'
        with open(os.path.join(http_tests_dir, test_file), 'rb') as f:
            test_data = f.read()

        for c in range(1, len(test_data) + 1):
            # Skip first `d` bytes - not interesting
            for d in range(c):

                # Create form parser.
                self.make('boundary')
                # Skip
                i = 0
                self.f.write(test_data[:d])
                i += d
                for x in range(d, len(test_data), c):
                    # Write a chunk to achieve condition
                    #     `i == data_length - 1`
                    # in boundary search loop (multipatr.py:1302)
                    b = test_data[x:x + c]
                    i += self.f.write(b)

                self.f.finalize()

                # Assert we processed everything.
                self.assertEqual(i, len(test_data))

                # Assert that our field is here.
                self.assert_field(b'field',
                                  b'0123456789ABCDEFGHIJ0123456789ABCDEFGHIJ')

    @slow_test
    def test_request_body_fuzz(self):
        """
        This test randomly fuzzes the request body to ensure that no strange
        exceptions are raised and we don't end up in a strange state.  The
        fuzzing consists of randomly doing one of the following:
            - Adding a random byte at a random offset
            - Randomly deleting a single byte
            - Randomly swapping two bytes
        """
        # Load test data.
        test_file = 'single_field_single_file.http'
        with open(os.path.join(http_tests_dir, test_file), 'rb') as f:
            test_data = f.read()

        iterations = 1000
        successes = 0
        failures = 0
        exceptions = 0

        print("Running %d iterations of fuzz testing:" % (iterations,))
        for i in range(iterations):
            # Create a bytearray to mutate.
            fuzz_data = bytearray(test_data)

            # Pick what we're supposed to do.
            choice = random.choice([1, 2, 3])
            if choice == 1:
                # Add a random byte.
                i = random.randrange(len(test_data))
                b = random.randrange(256)

                fuzz_data.insert(i, b)
                msg = "Inserting byte %r at offset %d" % (b, i)

            elif choice == 2:
                # Remove a random byte.
                i = random.randrange(len(test_data))
                del fuzz_data[i]

                msg = "Deleting byte at offset %d" % (i,)

            elif choice == 3:
                # Swap two bytes.
                i = random.randrange(len(test_data) - 1)
                fuzz_data[i], fuzz_data[i + 1] = fuzz_data[i + 1], fuzz_data[i]

                msg = "Swapping bytes %d and %d" % (i, i + 1)

            # Print message, so if this crashes, we can inspect the output.
            print("  " + msg)

            # Create form parser.
            self.make('boundary')

            # Feed with data, and ignore form parser exceptions.
            i = 0
            try:
                i = self.f.write(bytes(fuzz_data))
                self.f.finalize()
            except FormParserError:
                exceptions += 1
            else:
                if i == len(fuzz_data):
                    successes += 1
                else:
                    failures += 1

        print("--------------------------------------------------")
        print("Successes:  %d" % (successes,))
        print("Failures:   %d" % (failures,))
        print("Exceptions: %d" % (exceptions,))

    @slow_test
    def test_request_body_fuzz_random_data(self):
        """
        This test will fuzz the multipart parser with some number of iterations
        of randomly-generated data.
        """
        iterations = 1000
        successes = 0
        failures = 0
        exceptions = 0

        print("Running %d iterations of fuzz testing:" % (iterations,))
        for i in range(iterations):
            data_size = random.randrange(100, 4096)
            data = os.urandom(data_size)
            print("  Testing with %d random bytes..." % (data_size,))

            # Create form parser.
            self.make('boundary')

            # Feed with data, and ignore form parser exceptions.
            i = 0
            try:
                i = self.f.write(bytes(data))
                self.f.finalize()
            except FormParserError:
                exceptions += 1
            else:
                if i == len(data):
                    successes += 1
                else:
                    failures += 1

        print("--------------------------------------------------")
        print("Successes:  %d" % (successes,))
        print("Failures:   %d" % (failures,))
        print("Exceptions: %d" % (exceptions,))

    def test_bad_start_boundary(self):
        self.make('boundary')
        data = b'--boundary\rfoobar'
        with self.assertRaises(MultipartParseError):
            self.f.write(data)

        self.make('boundary')
        data = b'--boundaryfoobar'
        with self.assertRaises(MultipartParseError):
            i = self.f.write(data)

    def test_octet_stream(self):
        files = []
        def on_file(f):
            files.append(f)
        on_field = Mock()
        on_end = Mock()

        f = FormParser('application/octet-stream', on_field, on_file, on_end=on_end, file_name=b'foo.txt')
        self.assertTrue(isinstance(f.parser, OctetStreamParser))

        f.write(b'test')
        f.write(b'1234')
        f.finalize()

        # Assert that we only received a single file, with the right data, and that we're done.
        self.assertFalse(on_field.called)
        self.assertEqual(len(files), 1)
        self.assert_file_data(files[0], b'test1234')
        self.assertTrue(on_end.called)

    def test_querystring(self):
        fields = []
        def on_field(f):
            fields.append(f)
        on_file = Mock()
        on_end = Mock()

        def simple_test(f):
            # Reset tracking.
            del fields[:]
            on_file.reset_mock()
            on_end.reset_mock()

            # Write test data.
            f.write(b'foo=bar')
            f.write(b'&test=asdf')
            f.finalize()

            # Assert we only received 2 fields...
            self.assertFalse(on_file.called)
            self.assertEqual(len(fields), 2)

            # ...assert that we have the correct data...
            self.assertEqual(fields[0].field_name, b'foo')
            self.assertEqual(fields[0].value, b'bar')

            self.assertEqual(fields[1].field_name, b'test')
            self.assertEqual(fields[1].value, b'asdf')

            # ... and assert that we've finished.
            self.assertTrue(on_end.called)

        f = FormParser('application/x-www-form-urlencoded', on_field, on_file, on_end=on_end)
        self.assertTrue(isinstance(f.parser, QuerystringParser))
        simple_test(f)

        f = FormParser('application/x-url-encoded', on_field, on_file, on_end=on_end)
        self.assertTrue(isinstance(f.parser, QuerystringParser))
        simple_test(f)

    def test_close_methods(self):
        parser = Mock()
        f = FormParser('application/x-url-encoded', None, None)
        f.parser = parser

        f.finalize()
        parser.finalize.assert_called_once_with()

        f.close()
        parser.close.assert_called_once_with()

    def test_bad_content_type(self):
        # We should raise a ValueError for a bad Content-Type
        with self.assertRaises(ValueError):
            f = FormParser('application/bad', None, None)

    def test_no_boundary_given(self):
        # We should raise a FormParserError when parsing a multipart message
        # without a boundary.
        with self.assertRaises(FormParserError):
            f = FormParser('multipart/form-data', None, None)

    def test_bad_content_transfer_encoding(self):
        data = b'----boundary\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\nContent-Transfer-Encoding: badstuff\r\n\r\nTest\r\n----boundary--\r\n'

        files = []
        def on_file(f):
            files.append(f)
        on_field = Mock()
        on_end = Mock()

        # Test with erroring.
        config = {'UPLOAD_ERROR_ON_BAD_CTE': True}
        f = FormParser('multipart/form-data', on_field, on_file,
                       on_end=on_end, boundary='--boundary', config=config)

        with self.assertRaises(FormParserError):
            f.write(data)
            f.finalize()

        # Test without erroring.
        config = {'UPLOAD_ERROR_ON_BAD_CTE': False}
        f = FormParser('multipart/form-data', on_field, on_file,
                       on_end=on_end, boundary='--boundary', config=config)

        f.write(data)
        f.finalize()
        self.assert_file_data(files[0], b'Test')

    def test_handles_None_fields(self):
        fields = []
        def on_field(f):
            fields.append(f)
        on_file = Mock()
        on_end = Mock()

        f = FormParser('application/x-www-form-urlencoded', on_field, on_file, on_end=on_end)
        f.write(b'foo=bar&another&baz=asdf')
        f.finalize()

        self.assertEqual(fields[0].field_name, b'foo')
        self.assertEqual(fields[0].value, b'bar')

        self.assertEqual(fields[1].field_name, b'another')
        self.assertEqual(fields[1].value, None)

        self.assertEqual(fields[2].field_name, b'baz')
        self.assertEqual(fields[2].value, b'asdf')

    def test_max_size_multipart(self):
        # Load test data.
        test_file = 'single_field_single_file.http'
        with open(os.path.join(http_tests_dir, test_file), 'rb') as f:
            test_data = f.read()

        # Create form parser.
        self.make('boundary')

        # Set the maximum length that we can process to be halfway through the
        # given data.
        self.f.parser.max_size = len(test_data) / 2

        i = self.f.write(test_data)
        self.f.finalize()

        # Assert we processed the correct amount.
        self.assertEqual(i, len(test_data) / 2)

    def test_max_size_form_parser(self):
        # Load test data.
        test_file = 'single_field_single_file.http'
        with open(os.path.join(http_tests_dir, test_file), 'rb') as f:
            test_data = f.read()

        # Create form parser setting the maximum length that we can process to
        # be halfway through the given data.
        size = len(test_data) / 2
        self.make('boundary', config={'MAX_BODY_SIZE': size})

        i = self.f.write(test_data)
        self.f.finalize()

        # Assert we processed the correct amount.
        self.assertEqual(i, len(test_data) / 2)

    def test_octet_stream_max_size(self):
        files = []
        def on_file(f):
            files.append(f)
        on_field = Mock()
        on_end = Mock()

        f = FormParser('application/octet-stream', on_field, on_file,
                       on_end=on_end, file_name=b'foo.txt',
                       config={'MAX_BODY_SIZE': 10})

        f.write(b'0123456789012345689')
        f.finalize()

        self.assert_file_data(files[0], b'0123456789')

    def test_invalid_max_size_multipart(self):
        with self.assertRaises(ValueError):
            q = MultipartParser(b'bound', max_size='foo')


class TestHelperFunctions(unittest.TestCase):
    def test_create_form_parser(self):
        r = create_form_parser({'Content-Type': 'application/octet-stream'},
                               None, None)
        self.assertTrue(isinstance(r, FormParser))

    def test_create_form_parser_error(self):
        headers = {}
        with self.assertRaises(ValueError):
            create_form_parser(headers, None, None)

    def test_parse_form(self):
        on_field = Mock()
        on_file = Mock()

        parse_form(
            {'Content-Type': 'application/octet-stream',
             },
            BytesIO(b'123456789012345'),
            on_field,
            on_file
        )

        assert on_file.call_count == 1

        # Assert that the first argument of the call (a File object) has size
        # 15 - i.e. all data is written.
        self.assertEqual(on_file.call_args[0][0].size, 15)

    def test_parse_form_content_length(self):
        files = []
        def on_file(file):
            files.append(file)

        parse_form(
            {'Content-Type': 'application/octet-stream',
             'Content-Length': '10'
             },
            BytesIO(b'123456789012345'),
            None,
            on_file
        )

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].size, 10)



def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestFile))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestParseOptionsHeader))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestBaseParser))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestQuerystringParser))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestOctetStreamParser))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestBase64Decoder))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestQuotedPrintableDecoder))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestFormParser))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestHelperFunctions))

    return suite
