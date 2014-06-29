import tokenizer


MODIFIERS = ['const', 'volatile'] # XXX: are there others?

try:
    set
except NameError:
    from sets import Set as set


class CType(object):
    """
    A L{CType} represents a C/C++ type as a list of items.  Generally
    the items are L{Token}s, but some times they can be other
    L{CType}s (arguments of templated types, function pointer name and parameters).
    """
    __slots__ = 'tokens'
    def __init__(self, tokens=None):
        if tokens is None:
            self.tokens = []
        else:
            self.tokens = tokens

    def clone(self):
        return CType(list(self.tokens))

    def reorder_modifiers(self):
        """
        Reoder const modifiers, as rightward as possible without
        changing the meaning of the type.  I.e., move modifiers to the
        right until a * or & is found."""
        for modifier in MODIFIERS:
            self._reorder_modifier(modifier)

    def _reorder_modifier(self, modifier):
        tokens_moved = []
        while 1:
            reordered = False
            for token_i, token in enumerate(self.tokens):
                if isinstance(token, CType):
                    continue
                if token.name == modifier and token not in tokens_moved:
                    ## Reorder the token.  Note: we are mutating the
                    ## list we are iterating over, but it's ok because
                    ## we'll break the for unconditionally next.

                    self.tokens.pop(token_i)
                    
                    for new_pos in range(token_i, len(self.tokens)):
                        other_token = self.tokens[new_pos]
                        if isinstance(other_token, CType):
                            continue
                        if other_token.name in ['*', '&']:
                            self.tokens.insert(new_pos, token)
                            break
                    else:
                        self.tokens.append(token)
                        new_pos = -1

                    tokens_moved.append(token)
                    reordered = True
                    break
            if not reordered:
                break

    def remove_modifiers(self):
        """
        Remove modifiers from the toplevel type.  Return a set of modifiers removed.
        """
        retval = set()
        for modifier in MODIFIERS:
            if self._remove_modifier(modifier):
                retval.add(modifier)
        return retval

    def _remove_modifier(self, modifier):
        changed = True
        removed = False
        while changed:
            changed = False
            for token_i, token in enumerate(self.tokens):
                if isinstance(token, CType):
                    continue
                if token.name == modifier:
                    del self.tokens[token_i]
                    changed = True
                    removed = True
                    break
        return removed

    def remove_outer_modifier(self, modifier):
        """
        Remove the given modifier from the type, but only from the
        outer part and only until a first * or & is found, from right
        to left.
        """
        for token_i in range(len(self.tokens)-1, -1, -1):
            token = self.tokens[token_i]
            if isinstance(token, CType):
                continue
            if token.name == modifier:
                del self.tokens[token_i]
                return True
        return False

    def __str__(self):
        l = []
        first = True
        for token in self.tokens:
            if isinstance(token, tokenizer.Token):
                if token.name in "<,":
                    l.append(token.name)
                else:
                    if first:
                        l.append(token.name)
                    else:
                        l.append(' ' + token.name)
            else:
                assert isinstance(token, CType)
                if first:
                    l.append(str(token))
                else:
                    l.append(' ' + str(token))
            first = False
        return ''.join(l)


def _parse_type_recursive(tokens):
    ctype = CType()
    while tokens:
        token = tokens.pop(0)
        if token.name.startswith('::'):
            token.name = token.name[2:]
        if token.token_type == tokenizer.SYNTAX:
            if token.name in [',', '>', ')']:
                ctype.reorder_modifiers()
                return ctype, token
            elif token.name in ['<', '(']:
                ctype.tokens.append(token)
                while 1:
                    nested_ctype, last_token = _parse_type_recursive(tokens)
                    ctype.tokens.append(nested_ctype)
                    ctype.tokens.append(last_token)
                    assert token.token_type == tokenizer.SYNTAX
                    if last_token.name == ',':
                        continue
                    elif last_token.name in ['>', ')']:
                        break
                    else:
                        assert False, ("last_token invalid: %s" % last_token)
            else:
                ctype.tokens.append(token)
        else:
            ctype.tokens.append(token)
    ctype.reorder_modifiers()
    return ctype, None


def parse_type(type_string):
    """
    Parse a C type string.

    :param type_string: C type expression
    :returns: a L{CType} object representing the type
    """
    tokens = list(tokenizer.GetTokens(type_string + '\n'))
    ctype, last_token = _parse_type_recursive(tokens)
    assert last_token is None
    return ctype

def normalize_type_string(type_string):
    """
    Return a type string in a canonical format, with deterministic
    placement of modifiers and spacing.  Useful to make sure two type
    strings match regardless of small variations of representation
    that do not change the meaning.

    :param type_string: C type expression
    :returns: another string representing the same C type but in a canonical format

    >>> normalize_type_string('char *')
    'char *'
    >>> normalize_type_string('const foo::bar<const char*, zbr&>*')
    'foo::bar< char const *, zbr & > const *'
    >>> normalize_type_string('const ::bar*')
    'bar const *'
    >>> normalize_type_string('const char*const')
    'char const * const'
    >>> normalize_type_string('const char*const*const')
    'char const * const * const'
    >>> normalize_type_string('const std::map<std::string, void (*) (int, std::vector<zbr>) >')
    'std::map< std::string, void ( * ) ( int, std::vector< zbr > ) > const'
    """
    ctype = parse_type(type_string)
    return str(ctype)


class TypeTraits(object):
    """
    Parse a C type and gather some interesting properties.

    @ivar ctype: the original unmodified type (a L{CType} object, apply str() to obtain a type string).

    @ivar ctype_no_modifiers: the type with all modifiers (const, volatile, ...) removed (except from template arguments)

    @ivar type_is_const: True if the outermost type is const

    @ivar type_is_reference: True if the outermost type is a reference

    @ivar type_is_pointer:  True if the outermost type is a pointer

    @ivar target_is_const: True if the type is pointer or reference and the target is const

    @ivar target: if this is a pointer or reference type, a L{CType}
    representing the target, without modifiers.  If not pointer or
    reference, it is None.

    >>> t = TypeTraits("int")
    >>> print repr(str(t.ctype))
    'int'
    >>> print repr(str(t.ctype_no_modifiers))
    'int'
    >>> t.type_is_const
    False
    >>> t.type_is_pointer
    False
    >>> t.type_is_reference
    False
    >>> t.target is None
    True

    >>> t = TypeTraits("const int * const")
    >>> print repr(str(t.ctype))
    'int const * const'
    >>> print repr(str(t.ctype_no_modifiers))
    'int *'
    >>> print repr(str(t.ctype_no_const))
    'int const *'
    >>> t.type_is_const
    True
    >>> t.type_is_pointer
    True
    >>> t.type_is_reference
    False
    >>> t.target is None
    False
    >>> print repr(str(t.target))
    'int'
    >>> t.target_is_const
    True

    >>> t = TypeTraits("int * const")
    >>> print repr(str(t.ctype))
    'int * const'
    >>> print repr(str(t.ctype_no_modifiers))
    'int *'
    >>> print repr(str(t.ctype_no_const))
    'int *'
    >>> t.type_is_const
    True
    >>> t.type_is_pointer
    True
    >>> t.type_is_reference
    False
    >>> t.target is None
    False
    >>> print repr(str(t.target))
    'int'
    >>> t.target_is_const
    False

    >>> t = TypeTraits("const char *")
    >>> print repr(str(t.ctype))
    'char const *'
    >>> print repr(str(t.ctype_no_modifiers))
    'char *'
    >>> print repr(str(t.ctype_no_const))
    'char const *'
    >>> t.type_is_const
    False
    >>> t.type_is_pointer
    True
    >>> t.type_is_reference
    False
    >>> t.target is None
    False
    >>> print repr(str(t.target))
    'char'
    >>> t.target_is_const
    True

    >>> t = TypeTraits("char *")
    >>> print repr(str(t.ctype))
    'char *'
    >>> t.make_const()
    >>> print repr(str(t.ctype))
    'char * const'
    >>> t.make_target_const()
    >>> print repr(str(t.ctype))
    'char const * const'

    """

    def __init__(self, ctype):
        self.ctype = parse_type(ctype)
        self.ctype_no_modifiers = self.ctype.clone()
        self.ctype_no_modifiers.remove_modifiers()
        self.ctype_no_const = self.ctype.clone()
        tokens = list(self.ctype.tokens)
        tokens.reverse()
        ptr_ref_level = 0
        self.type_is_const = False
        self.type_is_reference = False
        self.type_is_pointer = False
        self.target_is_const = False
        self.target = None
        target_pos = None
        for pos, token in enumerate(tokens):
            if isinstance(token, CType):
                continue
            if token.name == 'const':
                if ptr_ref_level == 0:
                    self.type_is_const = True
                    const_removed = self.ctype_no_const.remove_outer_modifier('const')
                    assert const_removed
                elif ptr_ref_level == 1:
                    self.target_is_const = True
            elif token.name == '*':
                if ptr_ref_level == 0:
                    self.type_is_pointer = True
                    target_pos = pos + 1
                ptr_ref_level += 1
            elif token.name == '&':
                if ptr_ref_level == 0:
                    self.type_is_reference = True
                    target_pos = pos + 1
                ptr_ref_level += 1
        if target_pos is not None:
            target_tokens = tokens[target_pos:]
            target_tokens.reverse()
            self.target = CType(target_tokens)
            self.target.remove_modifiers()

    def make_const(self):
        """
        Add a const modifier to the type.  Has no effect if the type is already const.
        """
        if self.type_is_const:
            return
        self.type_is_const = True
        self.ctype.tokens.append(tokenizer.Token(tokenizer.NAME, "const", None, None))

    def make_target_const(self):
        """
        Add a const modifier to the type target.  Has no effect if the type target is already const.
        """
        assert self.type_is_pointer or self.type_is_reference
        if self.target_is_const:
            return
        self.target_is_const = True
        for tokens in self.ctype.tokens, self.ctype_no_const.tokens:
            for token_i in range(len(tokens)-1, -1, -1):
                token = tokens[token_i]
                if isinstance(token, CType):
                    continue
                elif token.name in ['*', '&']:
                    tokens.insert(token_i, tokenizer.Token(tokenizer.NAME, "const", None, None))
                    break
