
def test():
    yield 'foo'
    print('foo')
    yield 'bar'
    print('foo')
    yield 'baz'
    print('foo')

result = test()
for t in result:
    print('bar')
