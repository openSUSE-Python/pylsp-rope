class TestClass:
    def test_method(self):
        local_var = "local_value"
        print(f"Test method with {local_var}")


def standalone_function():
    return "standalone_result"


# This should be moveable
class_to_move = TestClass
