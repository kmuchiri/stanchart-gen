def time_to_sec (time_fig:str) -> float | None:
    '''
    Takes a given value of time, determines if it is minutes, seconds or hours and outputs the time in seconds
    
    param:
    time_fig str: a sting of a given value

    returns:
    float of time in seconds
    '''
    time_seg = time_fig.split(":")

    if len(time_seg) == 1:
        return float(time_seg[0])
    elif len(time_seg) == 2:
        return float(time_seg[0]) * 60 + float(time_seg[1])
    elif len(time_seg) == 3:
        return float(time_seg[0]) * 60 * 60 + float(time_seg[1]) * 60 + float(time_seg[2])
    else:
        return None
    
