"""
FontBakery callable is the wrapper for your custom check code.


Separation of Concerns Disclaimer:
While created specifically for running checks on fonts and font-families
this module has no domain knowledge about fonts. It can be used for any
kind of (document) checking. Please keep it so. It will be valuable for
other domains as well.
Domain specific knowledge should be encoded only in the Profile (Checks,
Conditions) and MAYBE in *customized* reporters e.g. subclasses.

"""
import inspect

from functools import update_wrapper, cached_property
from typing import Callable


class FontbakeryCallable:
    __wrapped__: Callable

    def __init__(self, func):
        self._args = None
        self._mandatoryArgs = None
        self._optionalArgs = None
        # must be set by sub class

        # this is set by update_wrapper
        # self.__wrapped__ = func

        # https://docs.python.org/2/library/functools.html#functools.update_wrapper
        # Update a wrapper function to look like the wrapped function.
        # ... assigns to the wrapper function’s __name__, __module__ and __doc__
        update_wrapper(self, func)

    def __repr__(self):
        return "<{}:{}>".format(
            type(self).__name__,
            getattr(self, "id", getattr(self, "name", super().__repr__())),
        )  # pylint: disable=consider-using-f-string

    @cached_property
    def args(self):
        return self.mandatoryArgs + self.optionalArgs

    @cached_property
    def mandatoryArgs(self):
        args = []
        # make follow_wrapped=True explicit, even though it is the default!
        sig = inspect.signature(self, follow_wrapped=True)
        for name, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty or param.kind not in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.POSITIONAL_ONLY,
            ):
                # has a default i.e. not mandatory or not positional of any kind

                # Debugging message:
                # print(f'[{param}]'
                #       f' {param.default is inspect.Parameter.empty}'
                #       f' param.kind: {param.kind}'
                #       f' param.default: {param.default}'
                #       f' BREAK')
                break
            args.append(name)
        return tuple(args)

    @cached_property
    def optionalArgs(self):
        args = []
        # make follow_wrapped=True explicit, even though it is the default!
        sig = inspect.signature(self, follow_wrapped=True)
        for name, param in sig.parameters.items():
            if param.default is inspect.Parameter.empty:
                # is a mandatory
                continue

            if param.kind not in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.POSITIONAL_ONLY,
            ):
                # no more positional of any kind

                # Debugging message:
                # print(f'[{param}]'
                #       f'{param.default is inspect.Parameter.empty}'
                #       f' param.kind: {param.kind}'
                #       f' param.default: {param.default}'
                #       f' BREAK')
                break
            args.append(name)
        return tuple(args)

    def __call__(self, *args, **kwds):
        """Each call to __call__ with the same arguments must return
        the same result.
        """
        return self.__wrapped__(*args, **kwds)

    def inject_globals(self, new_globals):
        self.__wrapped__.__globals__.update(new_globals)


def get_doc_desc(func, description, documentation):
    doc = inspect.getdoc(func) or ""

    doclines = doc.split("\n")

    if not description:
        description = []
        while len(doclines) and doclines[0]:
            # consume until first empty line
            description.append(doclines[0])
            doclines = doclines[1:]
        # This removes line breaks
        description = " ".join(description)

    # remove preceding empty lines
    while len(doclines) and not doclines[0]:
        doclines = doclines[1:]

    if not documentation and len(doclines):
        documentation = "\n".join(doclines) or None

    return description, documentation


class FontBakeryCheck(FontbakeryCallable):
    def __init__(
        self,
        checkfunc,
        id,  # pylint:disable=redefined-builtin
        description=None,  # short text, this is mandatory
        documentation=None,
        name=None,  # very short text
        conditions=None,
        rationale=None,  # long text explaining why this check is needed.
        # Using markdown, perhaps?
        proposal=None,  # An URL to the original proposal for this check.
        # This is typically a github issue or pull request.
        experimental=False,  # Experimental checks won't affect the process exit code
        severity=None,  # numeric value from 1=min to 10=max, denoting check severity
        configs=None,  # items from config[self.id] to inject into the check's namespace
        misc_metadata=None,  # Miscelaneous free-form metadata fields
        # Some of them may be promoted to 1st-class metadata fields
        # if they start being used by the check-runner.
        # Below are a few candidates for that:
        # affects=None,  # A list of tuples each indicating Browser/OS/Application
        #                # and the affected versions range.
    ):
        """This is the base class for all checks. It will usually
        not be used directly to create check instances, rather
        decorators which are factories will init this class.

        Arguments:
        checkfunc: callable, the check implementation itself.

        id: use reverse domain name notation as a namespace and a
        unique identifier (numbers or anything) but make sure that
        it **never** **ever** changes, that it is **unique until
        eternity**. This is meant to provide a way to track
        burn-down or regressions in a project over time and maybe
        to identify changed/updated check implementations for partial
        profile re-evaluation (in contrast to full profile evaluation)
        if the profile/check changed but not the font.

        description: text, used as one line short description
        read by humans

        conditions: a list of condition names that must be all true
        in order for this check to be executed. conditions are similar
        to checks, because they also inspect the check subject and they
        also belong to the profile. However, they do not get reported
        directly (there could be checks that report the result of a
        condition). Conditions are registered and referenced by name
        (like "isVariableFont").
        We may accept a python function for combining or negating a condition.
        It receives the condition values as arguments, queried by name
        via inspection, and returns True or False.

        documentation: text used as a detailed documentation to
        be read by humans (in markdown format).

        configs: a list of variable names. Their values are looked up the
        check-specific config (i.e. ``config[self.id]``), and assigned to
        global variables within the check's namespace. e.g. in a check called
        ``example.com/mytest``, setting ``configs = [ "hello" ]`` will create
        a variable called ``hello` and fill it with the value of
        ``config["example.com/mytest"]["hello"]``.
        """
        super().__init__(checkfunc)
        self.id = id
        self.conditions = conditions or []
        self.rationale = rationale
        self.description, self.documentation = get_doc_desc(
            checkfunc, description, documentation
        )
        self.configs = configs
        self.proposal = proposal
        self.experimental = experimental
        self.severity = severity
        if not self.description:
            raise TypeError("{} needs a description.".format(type(self).__name__))

    # This was problematic. See: https://github.com/fonttools/fontbakery/issues/2194
    # def __str__(self):
    #  return self.id


def condition(cls):
    if not inspect.isclass(cls):
        raise TypeError(f"Condition {cls.__name__} must be added to a class")

    def decorator(*args, **kwds):
        func = args[0]
        prop = cached_property(func)
        prop.__set_name__(cls, func.__name__)
        setattr(cls, func.__name__, prop)

    return decorator


def check(*args, **kwds):
    """Check wrapper, a factory for FontBakeryCheck

    Requires all arguments of FontBakeryCheck but not `checkfunc`
    which is passed via the decorator syntax.
    """

    def wrapper(checkfunc):
        return FontBakeryCheck(checkfunc, *args, **kwds)

    return wrapper


class Disabled:
    def __init__(self, func):
        self.func = func


def disable(func):
    return Disabled(func)
