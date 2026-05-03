import uuid
from django.db import models
from django.contrib.auth.models import User


class DungeonMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="Dungeon")
    width = models.IntegerField(default=20)
    height = models.IntegerField(default=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.width}x{self.height})"


class Tile(models.Model):
    class TileType(models.TextChoices):
        WALL = 'wall', 'Wall'
        FLOOR = 'floor', 'Floor'
        DOOR = 'door', 'Door'
        STAIRS_DOWN = 'stairs_down', 'Stairs Down'

    dungeon_map = models.ForeignKey(DungeonMap, on_delete=models.CASCADE, related_name='tiles')
    x = models.IntegerField()
    y = models.IntegerField()
    tile_type = models.CharField(max_length=20, choices=TileType.choices, default=TileType.WALL)
    is_visible = models.BooleanField(default=False)
    is_explored = models.BooleanField(default=False)

    class Meta:
        unique_together = ('dungeon_map', 'x', 'y')
        ordering = ['y', 'x']

    def __str__(self):
        return f"Tile({self.x},{self.y}) [{self.tile_type}]"

    @property
    def is_walkable(self):
        return self.tile_type in (self.TileType.FLOOR, self.TileType.DOOR, self.TileType.STAIRS_DOWN)


class Item(models.Model):
    class ItemType(models.TextChoices):
        WEAPON = 'weapon', 'Weapon'
        ARMOR = 'armor', 'Armor'
        POTION = 'potion', 'Potion'
        GOLD = 'gold', 'Gold'
        KEY = 'key', 'Key'

    dungeon_map = models.ForeignKey(DungeonMap, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    x = models.IntegerField()
    y = models.IntegerField()
    name = models.CharField(max_length=50)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    value = models.IntegerField(default=1, help_text="Damage for weapons, defense for armor, heal amount for potions")
    description = models.TextField(blank=True, default="")
    picked_up = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} at ({self.x},{self.y})"


class Entity(models.Model):
    class EntityType(models.TextChoices):
        MONSTER = 'monster', 'Monster'
        NPC = 'npc', 'NPC'

    dungeon_map = models.ForeignKey(DungeonMap, on_delete=models.CASCADE, related_name='entities')
    x = models.IntegerField()
    y = models.IntegerField()
    entity_type = models.CharField(max_length=20, choices=EntityType.choices, default=EntityType.MONSTER)
    name = models.CharField(max_length=50)
    hp = models.IntegerField(default=10)
    max_hp = models.IntegerField(default=10)
    attack = models.IntegerField(default=2)
    defense = models.IntegerField(default=0)
    is_alive = models.BooleanField(default=True)
    symbol = models.CharField(max_length=1, default='M', help_text="Display character")

    def __str__(self):
        return f"{self.name} ({self.hp}hp) at ({self.x},{self.y})"


class PlayerState(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='player_state')
    current_map = models.ForeignKey(DungeonMap, on_delete=models.CASCADE, related_name='players')
    x = models.IntegerField(default=1)
    y = models.IntegerField(default=1)
    hp = models.IntegerField(default=30)
    max_hp = models.IntegerField(default=30)
    attack = models.IntegerField(default=3)
    defense = models.IntegerField(default=1)
    level = models.IntegerField(default=1)
    xp = models.IntegerField(default=0)
    gold = models.IntegerField(default=0)
    inventory = models.JSONField(default=list, help_text="List of item IDs or names")
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Level {self.level} ({self.hp}/{self.max_hp}hp)"

    def add_item(self, item_name):
        if isinstance(self.inventory, list):
            self.inventory.append(item_name)
        else:
            self.inventory = [item_name]
        self.save()
