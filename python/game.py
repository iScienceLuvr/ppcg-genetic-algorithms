from __future__ import print_function

from board import Board
from random import Random
from specimen import Specimen
import player as Player
import sys
import trap
import coordinates
import time

#Pick one of the following:
#from graphical_display import Display  #Requires pygame
#from tkinter_display import Display #Requires tkinter
#from text_display import Display
from no_display import Display


if sys.version_info >= (3,):
    xrange = range

NUMBER_OF_BOARDS = 1
BOARD_WIDTH = coordinates.BOARD_WIDTH
BOARD_HEIGHT = coordinates.BOARD_HEIGHT

NUMBER_OF_SAFE_COLORS = 20
NUMBER_OF_COLORS = sum([trap_type.max_traps for trap_type in trap.trap_types])\
                   + NUMBER_OF_SAFE_COLORS

NUMBER_OF_TURNS = 10000

INITIAL_SPECIMENS = 15
SPECIMEN_LIFESPAN = 100
REPRODUCTION_RATE = 10
NUM_PARENTS = 2

DNA_LENGTH = 50
DNA_MAX_VALUE = (1 << DNA_LENGTH) - 1
DNA_CROSSOVER_RATE = .1
DNA_MUTATION_RATE = .01

VISION_WIDTH = 5
VISION_DISTANCE = int(VISION_WIDTH/2)
VISION = [[coordinates.Coordinate(x, y)
          for x in xrange(-VISION_DISTANCE, VISION_DISTANCE+1)]
          for y in xrange(VISION_DISTANCE, -VISION_DISTANCE-1, -1)]

RANDOM_SEED = 13722829


random = Random(RANDOM_SEED)

def sanitized(board):
    safe_squares = []
    for start_y in xrange(BOARD_HEIGHT):
        start_coordinate = coordinates.Coordinate(0, start_y)
        next_squares = {start_coordinate}
        visited_squares = set(next_squares)
        while True:
            neighbors = [direction+coordinate
                         for direction in coordinates.directions
                         for coordinate in next_squares]
            teleported = [board.get_square(neighbor).teleport + neighbor
                          for neighbor in neighbors]
            if any([square.at_finish() or square in safe_squares
                    for square in teleported]):
                safe_squares.append(start_coordinate)
                break
            alive = [square for square in teleported
                     if not board.get_square(square).killer]
            unvisited = [square for square in alive
                         if square not in visited_squares]
            if len(unvisited) == 0:
                break
            visited_squares.update(unvisited)
            next_squares = set(unvisited)
    return safe_squares




def initialize_board():
    colors = list(range(NUMBER_OF_COLORS))
    random.shuffle(colors)
    while True:
        board = Board(random.randrange(0, 10000000), colors)
        safe_squares = sanitized(board)
        if safe_squares:
            board.starting_squares = safe_squares
            break
        print("Bad board, retrying...")

    #add specimens
    for __ in xrange(INITIAL_SPECIMENS):
        board.add_specimen(
            Specimen(random.getrandbits(DNA_LENGTH), 0),
            random.choice(safe_squares))

    return board


def take_turn(board, turn_number, player):
    points = 0
    for coordinate, specimens in board.specimens.items():
        for specimen in specimens:
            #Send winners back to start
            if coordinate.at_finish():
                points += 1
                new_start_coords = random.choice(board.starting_squares)
                specimen.birth = turn_number
                specimen.bonus_fitness += coordinates.UNSAFE_BOARD_WIDTH
                if new_start_coords in board.next_specimens:
                    board.next_specimens[new_start_coords].append(specimen)
                else:
                    board.next_specimens[new_start_coords] = [specimen]
                continue
            #Kill specimens of old age
            if turn_number == specimen.birth + SPECIMEN_LIFESPAN:
                continue
            #calculate vision
            vision = [[board.get_color(coordinate+offset)
                      for offset in line] for line in VISION]
            #move specimen
            direction = player.take_turn(specimen.dna, vision)
            new_location = coordinate+direction
            new_square = board.get_square(new_location)
            if new_square.wall:
                new_square = board.get_square(coordinate)
                new_location = coordinate
            teleported = new_square.teleport+new_location
            if board.get_square(teleported).killer and not coordinate.at_finish():
                continue
            if teleported in board.next_specimens:
                board.next_specimens[teleported].append(specimen)
            else:
                board.next_specimens[teleported] = [specimen]

    #transfer next_specimens to be the current specimens
    board.update_specimens()
    return points


def score_specimen(coordinate, specimen):
    return coordinate.x + specimen.bonus_fitness + 1


def breed(board, current_turn):
    #Calculate the total height of all of the specimens
    total = 0
    for coordinate, specimens in board.specimens.items():
        for specimen in specimens:
            total += score_specimen(coordinate, specimen)
    #Pick random heights from the total height to find a parent
    selected_specimens = []
    for __ in xrange(NUM_PARENTS):
        count_down = random.randrange(total)
        for coordinate, specimens in board.specimens.items():
            for specimen in specimens:
                if specimen in selected_specimens:
                    continue
                count_down -= score_specimen(coordinate, specimen)
                if count_down < 0:
                    selected_specimens.append(specimen)
                    total -= score_specimen(coordinate, specimen)
                    break
            else:
                continue
            break


    #choose a random parent
    current_parent = random.choice(selected_specimens)
    new_dna = 0
    for position in reversed(xrange(DNA_LENGTH)):
        #randomly switch parents
        if random.random() < DNA_CROSSOVER_RATE:
            current_parent = random.choice(selected_specimens)
        #copy over dna from the chosen parent
        bit = current_parent.bit_at(position)
        #mutate some of that data
        if random.random() < DNA_MUTATION_RATE:
            bit = -bit+1
        new_dna = (new_dna << 1) + bit
    assert new_dna <= DNA_MAX_VALUE
    #create specimen with new dna
    board.add_specimen(
        Specimen(new_dna, current_turn),
        random.choice(board.starting_squares))


def check_for_life(board):
    return len(board.specimens) > NUM_PARENTS


def run():
    player = Player.PLAYER_TYPE()
    total_points = 0
    reproduction_counter = 0
    display = Display(BOARD_HEIGHT, BOARD_WIDTH)
    for board_number in xrange(NUMBER_OF_BOARDS):
        print("Running board #"+str(board_number+1)+"/"+str(NUMBER_OF_BOARDS))
        board = initialize_board()
        start = time.time()
        for turn_number in xrange(NUMBER_OF_TURNS):
            # Move
            total_points += take_turn(board, turn_number, player)
            if not check_for_life(board):
                break
            # Reproduce
            reproduction_counter += REPRODUCTION_RATE
            while reproduction_counter >= 1:
                reproduction_counter -= 1
                breed(board, turn_number)
            #Draw tiles
            for coordinate in board.get_changed_cells():
                display.draw_cell(coordinate, board)
            display.update()
            if not turn_number % int(NUMBER_OF_TURNS/100):
                population = 0
                for c, specimens in board.specimens.items():
                    population += len(specimens)
                print(str(int(turn_number*100/NUMBER_OF_TURNS))+"% "
                      +str(time.time()-start)+" sec - "
                      +str(total_points)+" points - Population: "+str(population))
        #Score remaining specimen
        for coordinate, specimen in board.specimens.items():
            if coordinate.at_finish():
                total_points += len(specimen)
    print("Your bot got "+str(total_points)+" points")


if __name__ == "__main__":
    run()
