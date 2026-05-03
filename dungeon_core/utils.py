import random
from dungeon_core.models import DungeonMap, Tile, Entity, Item


class DungeonGenerator:
    GRID_WIDTH = 20
    GRID_HEIGHT = 20
    MIN_ROOMS = 3
    MAX_ROOMS = 6
    MIN_ROOM_SIZE = 3
    MAX_ROOM_SIZE = 6

    def __init__(self, width=None, height=None):
        self.width = width or self.GRID_WIDTH
        self.height = height or self.GRID_HEIGHT
        self.grid = [['wall' for _ in range(self.width)] for _ in range(self.height)]
        self.rooms = []

    def generate_bsp(self):
        self._carve_rooms()
        self._connect_rooms()
        self._place_stairs()
        return self.grid

    def generate_random_walk(self, steps=300):
        x = random.randint(3, self.width - 4)
        y = random.randint(3, self.height - 4)
        self.grid[y][x] = 'floor'

        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        for _ in range(steps):
            dx, dy = random.choice(directions)
            nx, ny = x + dx, y + dy
            if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
                x, y = nx, ny
                self.grid[y][x] = 'floor'

        return self.grid

    def _carve_rooms(self):
        num_rooms = random.randint(self.MIN_ROOMS, self.MAX_ROOMS)
        for _ in range(num_rooms * 10):
            w = random.randint(self.MIN_ROOM_SIZE, self.MAX_ROOM_SIZE)
            h = random.randint(self.MIN_ROOM_SIZE, self.MAX_ROOM_SIZE)
            x = random.randint(1, self.width - w - 1)
            y = random.randint(1, self.height - h - 1)
            new_room = (x, y, w, h)

            if self._rooms_overlap(new_room):
                continue

            self._fill_room(new_room)
            self.rooms.append(new_room)

            if len(self.rooms) >= num_rooms:
                break

    def _rooms_overlap(self, room):
        x, y, w, h = room
        padding = 1
        for rx, ry, rw, rh in self.rooms:
            if not (x + w + padding < rx or x > rx + rw + padding or
                    y + h + padding < ry or y > ry + rh + padding):
                return True
        return False

    def _fill_room(self, room):
        x, y, w, h = room
        for dy in range(h):
            for dx in range(w):
                self.grid[y + dy][x + dx] = 'floor'

    def _connect_rooms(self):
        for i in range(len(self.rooms) - 1):
            x1, y1, w1, h1 = self.rooms[i]
            x2, y2, w2, h2 = self.rooms[i + 1]
            cx1, cy1 = x1 + w1 // 2, y1 + h1 // 2
            cx2, cy2 = x2 + w2 // 2, y2 + h2 // 2

            if random.random() < 0.5:
                self._carve_h_tunnel(cy1, cx1, cx2)
                self._carve_v_tunnel(cx2, cy1, cy2)
            else:
                self._carve_v_tunnel(cx1, cy1, cy2)
                self._carve_h_tunnel(cy2, cx1, cx2)

    def _carve_h_tunnel(self, y, x1, x2):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if 0 <= y < self.height and 0 <= x < self.width:
                self.grid[y][x] = 'floor'

    def _carve_v_tunnel(self, x, y1, y2):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if 0 <= y < self.height and 0 <= x < self.width:
                self.grid[y][x] = 'floor'

    def _place_stairs(self):
        if self.rooms:
            last_room = self.rooms[-1]
            sx = last_room[0] + last_room[2] // 2
            sy = last_room[1] + last_room[3] // 2
            self.grid[sy][sx] = 'stairs_down'

    def get_spawn_point(self):
        if self.rooms:
            first_room = self.rooms[0]
            return first_room[0] + first_room[2] // 2, first_room[1] + first_room[3] // 2
        return 1, 1

    def save_to_db(self, map_instance=None):
        if map_instance is None:
            map_instance = DungeonMap.objects.create(
                width=self.width,
                height=self.height,
            )

        tiles_to_create = []
        for y in range(self.height):
            for x in range(self.width):
                tile_type = self.grid[y][x]
                tiles_to_create.append(
                    Tile(
                        dungeon_map=map_instance,
                        x=x,
                        y=y,
                        tile_type=tile_type,
                    )
                )

        Tile.objects.bulk_create(tiles_to_create)

        spawn_x, spawn_y = self.get_spawn_point()

        return map_instance, spawn_x, spawn_y


def generate_dungeon(width=20, height=20, method='bsp'):
    generator = DungeonGenerator(width, height)

    if method == 'random_walk':
        generator.generate_random_walk(steps=400)
    else:
        generator.generate_bsp()

    return generator.save_to_db()


def populate_monsters(dungeon_map, count=5):
    floor_tiles = Tile.objects.filter(
        dungeon_map=dungeon_map,
        tile_type=Tile.TileType.FLOOR
    )
    tile_list = list(floor_tiles)
    random.shuffle(tile_list)

    monster_templates = [
        ('Rat', 5, 1, 0, 'r'),
        ('Goblin', 10, 2, 1, 'g'),
        ('Skeleton', 15, 3, 2, 's'),
        ('Orc', 20, 4, 2, 'O'),
        ('Troll', 30, 5, 3, 'T'),
    ]

    placed = 0
    for tile in tile_list:
        if placed >= count:
            break
        if tile.x <= 2 and tile.y <= 2:
            continue

        template = random.choice(monster_templates)
        name, hp, attack, defense, symbol = template
        Entity.objects.create(
            dungeon_map=dungeon_map,
            x=tile.x,
            y=tile.y,
            name=name,
            hp=hp,
            max_hp=hp,
            attack=attack,
            defense=defense,
            symbol=symbol,
        )
        placed += 1


def populate_items(dungeon_map, count=4):
    floor_tiles = Tile.objects.filter(
        dungeon_map=dungeon_map,
        tile_type=Tile.TileType.FLOOR
    )
    tile_list = list(floor_tiles)
    random.shuffle(tile_list)

    item_templates = [
        ('Short Sword', 'weapon', 3, 'A rusty short sword'),
        ('Leather Armor', 'armor', 2, 'Basic leather armor'),
        ('Health Potion', 'potion', 10, 'Restores 10 HP'),
        ('Gold Coins', 'gold', 5, 'Shiny gold coins'),
        ('Rusty Key', 'key', 1, 'An old rusty key'),
    ]

    placed = 0
    for tile in tile_list:
        if placed >= count:
            break

        template = random.choice(item_templates)
        name, item_type, value, description = template
        Item.objects.create(
            dungeon_map=dungeon_map,
            x=tile.x,
            y=tile.y,
            name=name,
            item_type=item_type,
            value=value,
            description=description,
        )
        placed += 1
