import requests

game_info = {
    "board": [
        [-1, -1, 9, -1, -1],
        [40, -1, -1, -1, 20],
        [-1, 40, -1, 16, -1],
        [40, -1, -1, -1, 24],
        [-1, -1, 20, -1, -1],
    ],
    "numbers_available": [1, 2, 3, 4, 5]
}

response = requests.post(
    "http://localhost:8000/levels/1",
    json={"game_info": game_info}
)
print(response.json())


[
    [-1, -1, -1],
    [4, 3, -1],
    [-1, -1, 2],
]

[1, 2, 3]