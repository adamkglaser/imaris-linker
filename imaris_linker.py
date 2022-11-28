import h5py
import numpy
import os
import glob

def write_numeric_attribute(group, attribute_name, number, dtype):
    """Write numeric attribute to imaris hdf5 file.
    :param group: hdf5 group object.
    :param attribute_name: name of attribute.
    :param number: value to be written.
    :param dtype: numeric datatype.
    .. code-block:: python
        write_numeric_attribute(info, 'NumberOfImages', 54, numpy.uint32)
    """
    # check if attribute already exists, delete if it does
    if h5py.h5a.exists(loc=group.id, name=attribute_name.encode('ascii')):
        h5py.h5a.delete(loc=group.id, name=attribute_name.encode('ascii'))
    # create attribute using high-level h5py api
    group.attrs.create(name=attribute_name, data=number, dtype=dtype)

def write_string_attribute(group, attribute_name, string):
    """Write string attribute to imaris hdf5 file.
    Note: Strings must be ascii formated, length 1, with nullterms.
    Note: Full low-level h5py API documentation available at https://api.h5py.org/index.html
    :param group: hdf5 group object.
    :param attribute_name: name of attribute.
    :param string: string to be written.
    .. code-block:: python
        write_string_attribute(info, 'ImageSizeX', '500')
    """
    # ascii encoded h5 string with length 1
    ascii_type=h5py.string_dtype(encoding='ascii', length=1)
    # create ascii encoded numpy string
    numpy_string=numpy.frombuffer(buffer=string.encode('ascii'), dtype=ascii_type)
    # copy of the null-terminated fixed-length string datatype
    type_id=h5py.h5t.TypeID.copy(h5py.h5t.C_S1)
    # set the total size of the datatype, in bytes.
    type_id.set_size(1)
    # set the padding type to null-terminated only (c style)
    type_id.set_strpad(h5py.h5t.STR_NULLTERM)
    # create simple dataspace for numpy string
    dataspace=h5py.h5s.create_simple((len(numpy_string),))
    # check if attribute already exists, delete if it does
    if h5py.h5a.exists(loc=group.id, name=attribute_name.encode('ascii')):
        h5py.h5a.delete(loc=group.id, name=attribute_name.encode('ascii'))
    # create attribute using low-level h5py api
    attribute=h5py.h5a.create(loc=group.id, name=attribute_name.encode('ascii'), tid=type_id, space=dataspace)
    # write numpy string to h5 attribute
    attribute.write(numpy_string, mtype=attribute.get_type())

def imaris_linker(path, filename, x_tiles, y_tiles, z_tiles, channels, color_range, color):
    """Generated combined imaris file with external links to imaris tile files.
    :param path: directory containing imaris hdf5 tile files.
    :param filename: combined imaris filename.
    :param x_tiles: number of x tiles in dataset.
    :param y_tiles: number of y tiles in dataset.
    :param z_tiles: number of z tiles in dataset.
    :param channels: number of channels in dataset.
    :param color_range: min/max color range values.
    :param color: rgb color values.
    .. code-block:: python
        imaris_linker('C:/example_data', 2, 3, 1, [488], [100, 500], [1, 1, 1])
    """
    # create output imaris file handle
    file_out=h5py.File(filename, 'w')
    # grab handle to file's parent group
    info=file_out['/']
    # write required attribute metadata for linking
    write_string_attribute(info, 'DataSetDirectoryName', 'DataSet')
    write_string_attribute(info, 'DataSetInfoDirectoryName', 'DataSetInfo')
    write_string_attribute(info, 'ImarisDataSet', 'ImarisDataSet')
    write_string_attribute(info, 'ImarisVersion', '5.5.0')
    write_numeric_attribute(info, 'NumberOfDataSets', x_tiles*y_tiles*z_tiles*len(channels), numpy.uint32)
    write_string_attribute(info, 'ThumbnailDirectoryName', 'Thumbnail')

    # initialize tile counter
    tile=0

    # loop over all expected imaris files
    for c in range(0, len(channels)):
        for z in range(0, z_tiles):
            for y in range(0, y_tiles):
                for x in range(0, x_tiles):
                    # create input imaris file handle
                    file_in=h5py.File(f'tile_x_{x:0>4d}_y_{y:0>4d}_z_{z:0>4d}_ch_{channels[c]}.ims', 'r')
                    # create output file group names based on tile #
                    if tile == 0:
                        data_name = 'DataSet'
                        data_info_name = 'DataSetInfo'
                    else:
                        data_name = f'DataSet{tile}'
                        data_info_name = f'DataSetInfo{tile}'
                    # copy datasetinfo from input file to combined output file
                    file_in.copy(source='DataSetInfo/Channel 0', dest=file_out, name=f'{data_info_name}/Channel 0')
                    file_in.copy(source='DataSetInfo/Image', dest=file_out, name=f'{data_info_name}/Image')
                    file_in.copy(source='DataSetInfo/ImarisDataSet', dest=file_out, name=f'{data_info_name}/ImarisDataSet')
                    file_in.copy(source='DataSetInfo/Log', dest=file_out, name=f'{data_info_name}/Log')
                    info=file_out[f'{data_info_name}/Image']
                    info.attrs.__delitem__('RecordingDate')
                    # update color and range for given tile
                    info=file_out[f'{data_info_name}/Channel 0']
                    # assume input color list goes r1 g1 b1 r2 g2 b2...
                    write_string_attribute(info, 'Color', f'{color[0+3*c]:.1f} {color[1+3*c]:.1f} {color[2+3*c]:.1f}')
                    write_string_attribute(info, 'ColorMode', 'BaseColor')
                    # assume input color range list goes min1 max1 min2 max2...
                    write_string_attribute(info, 'ColorRange', f'{color_range[0+2*c]:.1f} {color_range[1+2*c]:.1f}')
                    # create data group in output file
                    data=file_out.create_group(data_name)
                    # loop over all resolution levels
                    for r in range(0, len(file_in['DataSet'].keys())):
                        # create hard link within output file to data location in input file
                        data[f'ResolutionLevel {r}/TimePoint 0/Channel 0']=h5py.ExternalLink(f'./tile_x_{x:0>4d}_y_{y:0>4d}_z_{z:0>4d}_ch_{channels[c]}.ims', f'DataSet/ResolutionLevel {r}/TimePoint 0/Channel 0')
                    # close input file handle
                    file_in.close()
                    # increment tile
                    tile += 1
    # close output file handle
    file_out.close()

if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--path", type=str, default="C:")
    parser.add_argument("--filename", type=str, default="test.ims")
    parser.add_argument("--x_tiles", type=int, default=1)
    parser.add_argument("--y_tiles", type=int, default=1)
    parser.add_argument("--z_tiles", type=int, default=1)
    parser.add_argument("--channels", type=int, nargs='+', default=[488])
    parser.add_argument("--color_range", type=int, nargs='+', default=[0, 1000])
    parser.add_argument("--color", type=float, nargs='+', default=[0, 1, 1])
    args = parser.parse_args()
    os.chdir(args.path)
    # check input values
    files = glob.glob('./*.ims')
    if not files:
        raise ValueError('no ims files in specified directory.')
    if args.filename in files:
        raise ValueError('output filename is the same as ims file in directory.')
    if args.x_tiles < 0 or args.y_tiles < 0 or args.z_tiles < 0:
        raise ValueError('tiles cannot be negative.')
    if not isinstance(args.channels, list):
        raise TypeError('channels is not a list.')
    if not isinstance(args.color_range, list):
        raise TypeError('color range is not a list.')
    if not isinstance(args.color, list):
        raise TypeError('color is not a list.')
    if len(args.color) != 3*len(channels):
        raise ValueError('color must have 3 rgb values.')
    if len(args.color_range) != 2*len(channels):
        raise ValueError('color range must have 2 values (min/max).')
    imaris_linker(args.path, args.filename, args.x_tiles, args.y_tiles,
                  args.z_tiles, args.channels, args.color_range, args.color)
