It is therefore extremely important to write code that generalizes well and to *not* hardcode specific edge cases.

### Testing
- First write tests that reflect diversely how the language is supposed to work and how not.
- Check out other tests for language features (esp. test_misc.py) to see how tests are written. … It is fine to start with a fixed example which gives faster feedback (PBT tend to time out when the behavior is violated, feel free to abort test generation)
- Only run it at the end, prefer individual relevant tests before.

### Adding features
- Make sure to familiarize yourself with the way the visitor pattern is used for basically everything in the repo.
- If you rewrite a feature into existing features, make sure that the existing features are actually supported already.

- Add code there if it is supposed to extend the standard library of the language
