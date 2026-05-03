import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.db import transaction

from dungeon_core.models import DungeonMap, Tile, PlayerState, Entity, Item
from dungeon_core.utils import generate_dungeon, populate_monsters, populate_items

DIRECTIONS = {
    'north': (0, -1),
    'south': (0, 1),
    'east': (1, 0),
    'west': (-1, 0),
}


def get_or_create_player(request):
    session_id = request.session.session_key
    if not session_id:
        request.session.create()
        session_id = request.session.session_key

    user, _ = User.objects.get_or_create(
        username=f'player_{session_id}',
        defaults={'password': 'unused'}
    )

    try:
        player = PlayerState.objects.select_related('current_map').get(user=user)
        return player, False
    except PlayerState.DoesNotExist:
        with transaction.atomic():
            dungeon_map, spawn_x, spawn_y = generate_dungeon()
            populate_monsters(dungeon_map, count=5)
            populate_items(dungeon_map, count=4)

            player = PlayerState.objects.create(
                user=user,
                current_map=dungeon_map,
                x=spawn_x,
                y=spawn_y,
            )

        _reveal_tiles(player)
        return player, True


def _reveal_tiles(player, radius=3):
    tiles = Tile.objects.filter(
        dungeon_map=player.current_map,
        x__gte=player.x - radius,
        x__lte=player.x + radius,
        y__gte=player.y - radius,
        y__lte=player.y + radius,
    )
    for tile in tiles:
        dist = abs(tile.x - player.x) + abs(tile.y - player.y)
        if dist <= radius:
            tile.is_visible = True
            tile.is_explored = True
            tile.save()


def _hide_all_tiles(player):
    Tile.objects.filter(dungeon_map=player.current_map).update(is_visible=False)


@require_http_methods(["GET"])
def game_view(request):
    return render(request, 'game.html')


@require_http_methods(["GET"])
def get_map(request):
    player, is_new = get_or_create_player(request)
    _reveal_tiles(player)

    tiles = Tile.objects.filter(
        dungeon_map=player.current_map,
        is_explored=True
    )

    entities = Entity.objects.filter(
        dungeon_map=player.current_map,
        is_alive=True
    )

    items = Item.objects.filter(
        dungeon_map=player.current_map,
        picked_up=False
    )

    map_data = []
    for tile in tiles:
        tile_info = {
            'x': tile.x,
            'y': tile.y,
            'type': tile.tile_type,
            'visible': tile.is_visible,
        }
        map_data.append(tile_info)

    entity_data = []
    for entity in entities:
        entity_data.append({
            'x': entity.x,
            'y': entity.y,
            'name': entity.name,
            'hp': entity.hp,
            'max_hp': entity.max_hp,
            'symbol': entity.symbol,
        })

    item_data = []
    for item_obj in items:
        item_data.append({
            'x': item_obj.x,
            'y': item_obj.y,
            'name': item_obj.name,
            'type': item_obj.item_type,
        })

    return JsonResponse({
        'map': map_data,
        'entities': entity_data,
        'items': item_data,
        'player': {
            'x': player.x,
            'y': player.y,
            'hp': player.hp,
            'max_hp': player.max_hp,
            'attack': player.attack,
            'defense': player.defense,
            'level': player.level,
            'xp': player.xp,
            'gold': player.gold,
            'inventory': player.inventory,
        },
        'map_size': {
            'width': player.current_map.width,
            'height': player.current_map.height,
        },
        'message': 'Welcome to the dungeon!' if is_new else None,
    })


@csrf_exempt
@require_http_methods(["POST"])
def handle_action(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST

    action = data.get('action', data.get('direction', ''))
    player, _ = get_or_create_player(request)

    if action in DIRECTIONS:
        return _handle_movement(player, action)
    elif action == 'wait':
        return _handle_wait(player)
    elif action == 'descend' and _check_stairs(player):
        return _handle_descend(player)
    else:
        return JsonResponse({'status': 'error', 'message': f'Unknown action: {action}'})


def _handle_movement(player, direction):
    dx, dy = DIRECTIONS[direction]
    new_x = player.x + dx
    new_y = player.y + dy

    try:
        target_tile = Tile.objects.get(
            dungeon_map=player.current_map,
            x=new_x,
            y=new_y
        )
    except Tile.DoesNotExist:
        return JsonResponse({'status': 'blocked', 'message': 'There is a wall there.'})

    if not target_tile.is_walkable:
        return JsonResponse({'status': 'blocked', 'message': 'You hit a wall!'})

    enemy = Entity.objects.filter(
        dungeon_map=player.current_map,
        x=new_x,
        y=new_y,
        is_alive=True
    ).first()

    if enemy:
        return _handle_combat(player, enemy, direction)

    _hide_all_tiles(player)
    player.x = new_x
    player.y = new_y
    player.save()
    _reveal_tiles(player)

    item = Item.objects.filter(
        dungeon_map=player.current_map,
        x=new_x,
        y=new_y,
        picked_up=False
    ).first()

    message = f"You move {direction}."
    events = []

    if item:
        item.picked_up = True
        item.save()
        player.add_item(item.name)

        if item.item_type == Item.ItemType.WEAPON:
            player.attack += item.value
            events.append(f"Picked up {item.name}! Attack +{item.value}")
        elif item.item_type == Item.ItemType.ARMOR:
            player.defense += item.value
            events.append(f"Picked up {item.name}! Defense +{item.value}")
        elif item.item_type == Item.ItemType.POTION:
            heal = min(item.value, player.max_hp - player.hp)
            player.hp += heal
            events.append(f"Drank {item.name}! Healed {heal} HP")
        elif item.item_type == Item.ItemType.GOLD:
            player.gold += item.value
            events.append(f"Picked up {item.value} gold!")
        else:
            events.append(f"Picked up {item.name}!")

        player.save()

    return JsonResponse({
        'status': 'success',
        'player_pos': [player.x, player.y],
        'message': message,
        'events': events,
        'player': {
            'hp': player.hp,
            'max_hp': player.max_hp,
            'attack': player.attack,
            'defense': player.defense,
            'level': player.level,
            'xp': player.xp,
            'gold': player.gold,
        },
    })


def _handle_combat(player, enemy, direction):
    player_damage = max(1, player.attack - enemy.defense)
    enemy.hp -= player_damage

    message = f"You attack {enemy.name} for {player_damage} damage!"
    events = []

    if enemy.hp <= 0:
        enemy.is_alive = False
        enemy.save()
        xp_gain = enemy.max_hp
        player.xp += xp_gain
        message += f" {enemy.name} defeated! +{xp_gain} XP"

        if _check_level_up(player):
            events.append(f"Level up! You are now level {player.level}!")
    else:
        enemy.save()
        enemy_damage = max(1, enemy.attack - player.defense)
        player.hp -= enemy_damage
        message += f" {enemy.name} hits back for {enemy_damage} damage!"

        if player.hp <= 0:
            player.hp = 0
            player.save()
            return JsonResponse({
                'status': 'dead',
                'message': f"You have been slain by {enemy.name}! Refresh to start a new game.",
                'player': {'hp': 0},
            })

    player.save()

    return JsonResponse({
        'status': 'combat',
        'message': message,
        'events': events,
        'player': {
            'hp': player.hp,
            'max_hp': player.max_hp,
            'xp': player.xp,
            'level': player.level,
        },
    })


def _check_level_up(player):
    xp_threshold = player.level * 20
    if player.xp >= xp_threshold:
        player.level += 1
        player.max_hp += 5
        player.hp = player.max_hp
        player.attack += 1
        player.defense += 1
        player.save()
        return True
    return False


def _handle_wait(player):
    _hide_all_tiles(player)
    _reveal_tiles(player)

    if player.hp < player.max_hp:
        player.hp += 1
        player.save()

    return JsonResponse({
        'status': 'success',
        'message': 'You wait and recover 1 HP.',
        'player': {'hp': player.hp, 'max_hp': player.max_hp},
    })


def _check_stairs(player):
    return Tile.objects.filter(
        dungeon_map=player.current_map,
        x=player.x,
        y=player.y,
        tile_type=Tile.TileType.STAIRS_DOWN
    ).exists()


def _handle_descend(player):
    with transaction.atomic():
        new_map, spawn_x, spawn_y = generate_dungeon()
        player.current_map = new_map
        populate_monsters(new_map, count=5 + player.level)
        populate_items(new_map, count=4 + player.level)

        player.x = spawn_x
        player.y = spawn_y
        player.save()

    _reveal_tiles(player)

    return JsonResponse({
        'status': 'descended',
        'message': f"You descend to dungeon level {player.level}!",
        'player_pos': [player.x, player.y],
    })
