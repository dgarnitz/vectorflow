text = "This is a sample snippet of text that will be used to test embeddings APIs"
with open("test_long_text.txt", "w") as file:
    for _ in range(12000):
        file.write(text + "\n")
